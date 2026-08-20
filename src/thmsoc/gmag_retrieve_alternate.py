"""
gmag_retrieve_alternate

retrieves GMAG data from alternate sources to supplement AE index calculation
"""
import datetime as dt
from thmsoc.url_retrieve_file import url_retrieve_file
from pathlib import Path
import tomli
import obspy
from obspy.clients.fdsn import Client as fdsn_client
from obspy.clients.fdsn.header import FDSNNoDataException
from obspy.clients.fdsn.header import FDSNException
from obspy import UTCDateTime
from thmsoc import simple_daterange
from urllib3 import BaseHTTPResponse
import shutil

def midcenlon_to_tenthsmineast(midcenlon_deg):
    if midcenlon_deg < 0:
        abslon = midcenlon_deg+360.0
    else:
        abslon = midcenlon_deg
    frac_turn = abslon / 360.0
    tenthsmineast = frac_turn * 21600 * 10
    return tenthsmineast

def retrieve_alt_file(
        scode:str,
        date:dt.date, 
        data_root:str | Path,
        mirror_dir:str | Path | None = None) -> dict:
    # determine which retrieval method to use from the station code
    # TODO: this could use pyspedas gmag to get the gmag metadata to find group name
    # TODO: figure out if we want to mirror the 1 minute lrv and snkq data
    print(f"Retrieving {scode} data for {date.strftime('%Y-%m-%d')}...")

    retrieval_attempt_result = {"error_status":""}
    group_str = ""
    waveform_kwargs={}
    header_vals={}
    decbas_deg = 0.0
    match scode.lower():
        case "snkq":
            group_str = "nrcan"
            waveform_kwargs = {
                "station":"SNK",
                "network":'C2',
                "location":'R1',
                "channel":'UFX,UFY,UFZ,UFF'
            }
            header_vals = {
                "Source of Data":"Natural Resources Canada (NRCAN)",
                "Station Name":"Sanikiluaq",
                "IAGA CODE":"SNKQ",
                "Geodetic Latitude":"56.5", # can update from GMAG dict
                "Geodetic Longitude":"280.8",
                "Elevation":"",
                "Reported":"XYZF",
                "Sensor Orientation":"XYZ",
                "Digital Sampling":"0.5 second",
                "Data Interval Type":"1-minute",
                "Data Type":"variation"
            }
            decbas_deg = -14.9
        case "lrv":
            group_str = "lrv"
    if isinstance(data_root,str):
        data_root = Path(data_root)
    # data root should be /disks/themisdata
    workdir = Path(f"{data_root}/workdir/gmag/alt_remote_sources/{group_str}")
    workdir.mkdir(parents=True, exist_ok=True)
    try:
        match group_str:
            case "nrcan":
                try:
                    client = fdsn_client(group_str.upper())
                    st = client.get_waveforms(
                        attach_response=False,
                        starttime=UTCDateTime(date.strftime('%Y-%m-%dT00:00:00.000')), 
                        endtime=UTCDateTime((date + dt.timedelta(days = 1) - dt.timedelta(minutes = 1)).strftime('%Y-%m-%dT%H:%M:%S.%f')),
                        **waveform_kwargs)
                    channel_list = [substring.strip() for substring in waveform_kwargs["channel"].split(",")]
                    stream_list = []
                    time_list = []
                    for cha in channel_list:
                        if isinstance(st,obspy.Stream):
                            tmp = st.select(channel=cha,**{x: waveform_kwargs[x] for x in waveform_kwargs if x != "channel"}) 
                            tmp.merge(fill_value=99999)
                            #stream_data_arr = tmp.traces[0].data
                            #stream_data_arr[stream_data_arr==np.nan] = 99999
                            stream_list.append(tmp.traces[0].data)
                            time_list.append(tmp.traces[0].times("utcdatetime"))
                        else:
                            raise TypeError(
                                "get_waveforms did not return obspy.Stream object.",
                                "get_waveforms did not return obspy.Stream object")
                    # for each stream data and time array, create iaga2002 format text file using THEMIS naming convention
                    if not (time_list[0].all()==time_list[1].all()==time_list[2].all()==time_list[3].all()):
                        raise ValueError(
                            "ERROR! Different times found. Could not establish baseline. ",
                            "Differing times")
                    header_dict = {
                        "Format":"IAGA-2002"
                    }
                    header_dict.update(header_vals)
                    header_keys=[
                        "Format",
                        "Source of Data",
                        "Station Name",
                        "IAGA CODE",
                        "Geodetic Latitude", # can update from GMAG dict
                        "Geodetic Longitude",
                        "Elevation",
                        "Reported",
                        "Sensor Orientation",
                        "Digital Sampling",
                        "Data Interval Type",
                        "Data Type"
                    ]
                    header_str=""
                    for key_name in header_keys:
                        header_str += " " + key_name.ljust(23) + str(header_dict[key_name]).ljust(45) + "|" + "\n"
                    header_str += " " + ("# DECBAS").ljust(23) + (("%.0f" % midcenlon_to_tenthsmineast(decbas_deg)).ljust(45)) + "|" + "\n"
                    header_str += " " + ("# Data relayed via GOES primary").ljust(23+45) + "|" + "\n"
                    header_str += (
                        " " + ("#").ljust(23+45) + "|" + "\n"
                        " " + ("#").ljust(23+45) + "|" + "\n"
                        " " + ("#").ljust(23+45) + "|" + "\n"
                        " " + ("#").ljust(23+45) + "|" + "\n"
                        " " + ("#").ljust(23+45) + "|" + "\n"
                        " " + ("#").ljust(23+45) + "|" + "\n"
                        " " + ("#").ljust(23+45) + "|" + "\n"
                    )
                    header_str += "DATE".ljust(11) + "TIME".ljust(13) + "DOY".ljust(8)
                    header_str += (header_dict["IAGA CODE"] + "X").ljust(10)
                    header_str += (header_dict["IAGA CODE"] + "Y").ljust(10)
                    header_str += (header_dict["IAGA CODE"] + "Z").ljust(10)
                    header_str += (header_dict["IAGA CODE"] + "F").ljust(7)
                    header_str += "|"
                    data_str_list = [
                        "".join([
                            f"{time_list[0][data_idx].datetime.strftime('%Y-%m-%d').ljust(11)}",
                            f"{time_list[0][data_idx].datetime.strftime('%H:%M:%S.%f')[:-3].ljust(13)}",
                            f"{time_list[0][data_idx].datetime.strftime('%j').ljust(8)}",
                            str(("%.2f" % stream_list[0][data_idx]).ljust(10)),
                            str(("%.2f" % stream_list[1][data_idx]).ljust(10)),
                            str(("%.2f" % stream_list[2][data_idx]).ljust(10)),
                            str(("%.2f" % stream_list[3][data_idx]).ljust(7))    
                        ]) for data_idx in range(len(time_list[0]))]
                    data_str = "\n".join(data_str_list)
                    iaga_list = [header_str,data_str]
                    iaga_str = "\n".join(iaga_list) + "\n"
                    fn = "".join([
                        f"{scode.lower()}_1min",
                        f"{date.strftime('%Y%m%d')}",
                        "vmin",
                        ".min"
                    ])
                    output_filepath = Path(f"{workdir}/{fn}")
                    output_filepath.unlink(missing_ok=True)
                    output_file = open(output_filepath, "x")
                    output_file.close()
                    with open(output_filepath, "a") as of:
                            of.write(iaga_str)
                    if mirror_dir is not None:
                        if isinstance(mirror_dir,str):
                            mirror_dir=Path(mirror_dir)
                        mirror_dir = mirror_dir / f"{date.strftime('%Y')}" / f"{date.strftime('%m')}"
                        mirror_dir.mkdir(parents=True, exist_ok=True)
                        shutil.copy(output_filepath,mirror_dir / f"{fn}")
                except FDSNNoDataException:
                    raise ValueError("ERROR: Data not available for this date.","No data for this date")
                except FDSNException as error:
                    match error.status_code:
                        case "404":
                            raise ValueError("ERROR: Webpage not found!","Webpage not found error")
            case "lrv":
                fn = "".join([
                    "lrv_1min",
                    f"{date.year}"[-2:],
                    f"{date.strftime("%b")}".lower(),
                    ".min"
                ])        
                url = f"http://cygnus.rhi.hi.is/~halo/UCLA/{date.year}/{fn}"
                # URL contains ascii text which we can write to file.
                output_filepath = Path(f"{workdir}/{fn}")
                bytes_response = url_retrieve_file(
                    url,
                    out_filename=output_filepath,
                    format="bytes")
                if isinstance(bytes_response,BaseHTTPResponse):
                    string_response=bytes_response.data.decode('utf-8')
                else:
                    raise TypeError("Response must be BaseHTTPResponse object","Incorrect response object type")
                output_filepath.unlink(missing_ok=True)
                with open(output_filepath, "a") as of:
                        of.write(string_response)
                if mirror_dir is not None:
                    if isinstance(mirror_dir,str):
                        mirror_dir=Path(mirror_dir)
                    mirror_dir = mirror_dir / f"{date.strftime('%Y')}" / f"{date.strftime('%m')}"
                    mirror_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copy(output_filepath,mirror_dir / f"{fn}")
        return retrieval_attempt_result
    except ValueError as error:
        print(error.args[0] + " File could not be written; Aborting file retrieval...")
        #out_dict["error_status"] = error.args[1]
        retrieval_attempt_result["error_status"] = error.args[1]
    except TypeError as error:
        print(error.args[0] + " File could not be written; Aborting file retrieval...")
        #out_dict["error_status"] = error.args[1]
        retrieval_attempt_result["error_status"] = error.args[1]
    return retrieval_attempt_result

def run_gmag_retrieve_alternate(
        station_code:str | list[str], 
        start_date: str, 
        end_date: str,
        mirror_dir:str | Path | None = None,
        issue_list_fp: str | Path | None = None):
    main_start_time = dt.datetime.now()
    str_datetime_run = main_start_time.strftime('%Y%m%d_%H%M%S')  
    
    thmsoc_python_root = Path(__file__).resolve().parent.parent.parent
    thmsoc_python_config = thmsoc_python_root / "thmsoc_python_config.toml"
    try:
        with open(thmsoc_python_config, "rb") as f:
            toml_dict = tomli.load(f)
            OUTPUT_DATAROOT = Path(toml_dict["paths"]["output_dataroot"])
    except FileNotFoundError:
        OUTPUT_DATAROOT = Path("/disks/themisdata")
    
    if type(station_code) == str:
        scodes = [station_code]
    else:
        scodes = station_code
    
    dt_start_date = dt.datetime.strptime(start_date,'%Y-%m-%d')
    dt_end_date = dt.datetime.strptime(end_date,'%Y-%m-%d')
    missing_file_list = ""
    for scode in scodes:
        result_dict = {"error_status":""}
        match scode:
            case "lrv":
                # use monthly mode:
                dates_monthly_unsorted = []
                for current_date in simple_daterange(start = dt_start_date, end = dt_end_date):
                    dates_monthly_unsorted.append(dt.datetime.strptime(current_date.strftime("%Y-%m-01"),"%Y-%m-%d"))
                dates_monthly = sorted(set(dates_monthly_unsorted))
                #dates_monthly = sorted(set([dt.datetime.strptime(x.strftime("%Y-%m-01"),"%Y-%m-%d") for x in dates_daily]))
                for current_date in dates_monthly:
                    result_dict = retrieve_alt_file(scode=scode, date=current_date, data_root=OUTPUT_DATAROOT,mirror_dir=mirror_dir)
                    if result_dict["error_status"] != "":
                        missing_file_list += "Station: " + (scode.upper() + ",").ljust(5) + " Date: "+ current_date.strftime('%Y-%m-%d') +", Issue: " + result_dict["error_status"] + "\n"
            case _:
                # use daily mode:    
                for current_date in simple_daterange(start = dt_start_date, end = dt_end_date):
                    result_dict = retrieve_alt_file(scode=scode, date=current_date, data_root=OUTPUT_DATAROOT,mirror_dir=mirror_dir)
                    if result_dict["error_status"] != "":
                        missing_file_list += "Station: " + (scode.upper() + ",").ljust(5) + " Date: "+ current_date.strftime('%Y-%m-%d') +", Issue: " + result_dict["error_status"] + "\n"
    if missing_file_list != "":
        print("Retrieval was attempted for the following files, but failed for the following reasons: ")
        print(missing_file_list)
        # Make directory if it doesn't exist:
        if (issue_list_fp is not None) and (issue_list_fp != ""):
            if isinstance(issue_list_fp,str):
                failed_list_fp = Path(issue_list_fp)
            else:
                failed_list_fp = issue_list_fp
        else:
            failed_list_p = OUTPUT_DATAROOT.joinpath('process_logs','gmag','webdownloads','mag','alt_remote_sources')
            failed_list_p.mkdir(parents=True, exist_ok=True)
            failed_list_fp = failed_list_p.joinpath(f"failed_list{str_datetime_run}.txt")
        # Create file and print missing file list to file:
        failed_list_fp.unlink(missing_ok=True)
        failedf = open(failed_list_fp, "x")
        failedf.close()
        with open(failed_list_fp, "a") as of:
            print(missing_file_list, file=of)
        print(f"Wrote missing files to: {failed_list_fp}")
        return 1
    else:
        return 0

if __name__ == "__main__":
    run_gmag_retrieve_alternate(station_code=["snkq"],start_date="2026-01-01",end_date="2026-01-06")