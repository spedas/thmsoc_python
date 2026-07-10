"""
gmag_retrieve_alternate

retrieves GMAG data from alternate sources to supplement AE index calculation
"""
import datetime as dt
from thmsoc.url_construct_web_query import url_construct_web_query
from thmsoc.url_retrieve_file_bytes import retrieve_file_from_url
from pathlib import Path
import tomli
import numpy as np
from obspy.clients.fdsn import Client
from obspy import UTCDateTime

def midcenlon_to_tenthsmineast(midcenlon_deg):
    if midcenlon_deg < 0:
        abslon = midcenlon_deg+360.0
    else:
        abslon = midcenlon_deg
    frac_turn = abslon / 360.0
    tenthsmineast = frac_turn * 21600 * 10
    return tenthsmineast

def retrieve_alt_file(scode:str, date:dt.datetime, tmp_root:Path=Path("")):
    # determine which retrieval method to use from the station code
    # TODO: this could use pyspedas gmag to get the gmag metadata to find group name
    group_str = ""
    waveform_kwargs={}
    header_vals={}
    decbas_deg = 0.0
    if scode.lower()=="snkq":
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


    proc_dir = Path(f"{tmp_root}/retrieve_alternate/{group_str}")
    proc_dir.mkdir(parents=True, exist_ok=True)

    filenames = []
    match group_str:
        case "nrcan":
            client = Client(group_str.upper())
            st = client.get_waveforms(
                attach_response=True,
                **waveform_kwargs,
                starttime=UTCDateTime(date.strftime('%Y-%m-%dT00:00:00.000')), 
                endtime=UTCDateTime((date + dt.timedelta(days = 1) - dt.timedelta(minutes = 1)).strftime('%Y-%m-%dT%H:%M:%S.%f')))
            channel_list = [substring.strip() for substring in waveform_kwargs["channel"].split(",")]
            stream_list = []
            time_list = []
            for cha in channel_list:
                tmp = st.select(channel=cha,**{x: waveform_kwargs[x] for x in waveform_kwargs if x != "channel"}) 
                tmp.merge(fill_value=99999)
                #stream_data_arr = tmp.traces[0].data
                #stream_data_arr[stream_data_arr==np.nan] = 99999
                stream_list.append(tmp.traces[0].data)
                time_list.append(tmp.traces[0].times("utcdatetime"))
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
            
            output_filepath = Path(f"{proc_dir}/{scode.lower()}{date.strftime('%Y%m%d')}vmin.min")

            output_filepath.unlink(missing_ok=True)
            output_file = open(output_filepath, "x")
            output_file.close()
            
            with open(output_filepath, "a") as of:
                    of.write(iaga_str)
            
            print("done")
    return

def run_gmag_retrieve_alternate(scode:str, date:str | dt.datetime | list[str | dt.datetime]):
    thmsoc_python_root = Path(__file__).resolve().parent.parent.parent
    thmsoc_python_config = thmsoc_python_root / "thmsoc_python_config.toml"
    try:
        with open(thmsoc_python_config, "rb") as f:
            toml_dict = tomli.load(f)
            OUTDATAROOT = Path(toml_dict["paths"]["output_dataroot"])
            TEMPROOT = Path(toml_dict["paths"]["temproot"])
    except FileNotFoundError:
        OUTDATAROOT = Path("/disks/themisdata")
        TEMPROOT = Path("/mydisks/home/thmsoc/thmsoc_python")
    
    date_list = [dt.datetime.now()]
    if type(date) == dt.datetime:
        date_list = [date]
    elif type(date) == str:
        date_list = [dt.datetime.strptime(date,'%Y-%m-%d')]
    elif type(date) == list[str]:
        date_list = [dt.datetime.strptime(date_str,'%Y-%m-%d') for date_str in date]
    
    for date_current in date_list:
        retrieve_alt_file(scode=scode, date=date_current, tmp_root=TEMPROOT)
        
    return

if __name__ == "__main__":
    run_gmag_retrieve_alternate(scode="snkq",date="2026-01-20")