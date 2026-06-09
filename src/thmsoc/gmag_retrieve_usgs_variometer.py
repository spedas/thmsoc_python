# src/thmsoc/gmag_retrieve_usgs_variometer.py
import re
import numpy
import datetime as dt
import json
import tomli
import urllib3
import xml.etree.ElementTree as ET
from pathlib import Path
from concurrent import futures
from thmsoc import args_to_startend, batch_daterange

def str_list_max(in_list:list[str]) -> str: 
    if len(in_list) == 0:
        return ""
    else:
        return max(in_list)

def construct_web_query(
        web_scheme='https',
        web_netloc='',
        web_path='',
        query_list:list=[tuple],
        query_separator='&',
        web_fragment=''
        ):
    '''
    construct_web_query assumes query_list is an iterable, where each element is a tuple containing the query parameter name and an iterable with one or more elements, which will be populated into the query individually
    '''
    web_query=''
    if len(query_list) > 0:
        web_query += "?"
        for query_idx in range(len(query_list)):
            # New query field
            # Get query name and value list
            query_name,values = query_list[query_idx]
            # After the first query, separate the queries
            if query_idx > 0:
                web_query += query_separator
            # Even queries without values get query names
            web_query += query_name
            # If the query has a value, use an equals:
            if len(values) > 0:
                web_query += "="
                # Then place each element after the equals, comma separated:
                for value_idx in range(len(values)):
                    if value_idx > 0:
                        web_query += query_separator + query_name + "=" #","
                    web_query += values[value_idx]    
    return web_scheme+"://"+web_netloc+web_path+web_query+web_fragment

def construct_usgs_query(
        station_code, 
        start_datetime: dt.datetime, 
        end_datetime: dt.datetime, 
        sampling_period, 
        elements_list=['X','Y','Z'],
        usgs_remote_source_path='/ws/algorithms/filter/',
        data_format = 'json'
        ):
    '''
    construct URLs which query USGS server
    '''
    usgs_netloc='geomag.usgs.gov'
    usgs_path=usgs_remote_source_path
    usgs_query_list=[
        ('elements',elements_list),
        ('format',[data_format]), # was formerly 'iaga2002'
        ('id',[get_source_alias(station_code).upper()]),
        ('type',['variation']),
        ('starttime',[start_datetime.strftime('%Y-%m-%dT%H:%M:%S.%fZ')[:-4]]),
        ('endtime',[end_datetime.strftime('%Y-%m-%dT%H:%M:%S.%fZ')[:-4]]),
        ('output_sampling_period',[sampling_period]),
        ('starttime_only',["True"])
    ]
    return construct_web_query(web_netloc=usgs_netloc,web_path=usgs_path,query_list=usgs_query_list)

def sql_insert_update_query(db_table:str, in_dict:dict) -> str:
    '''
    create an sql update query from dict containing fields and associated values
    '''
    query_str = 'INSERT INTO '
    query_str += db_table + '(site,DataDate,'
    query_values_str = '"' + in_dict["site"] + '","' + in_dict["DataDate"] + '",'
    query_update_str = ''
    for key_name in in_dict:
        if key_name != "site" and key_name != "DataDate" and key_name != "error_status":
            key_val = in_dict[key_name]
            if key_val != "":
                query_str += key_name + ','
                query_values_str += '"' + key_val + '",'
                query_update_str += key_name + ' = "' + key_val + '",'
    # remove last comma
    if query_str != "": query_str = query_str[:-1]
    if query_values_str != "": query_values_str = query_values_str[:-1]
    if query_update_str != "": query_update_str = query_update_str[:-1]
    
    query_str += ') VALUES ('
    query_str += query_values_str
    query_str += ') ON DUPLICATE KEY UPDATE '
    query_str += query_update_str + ';'
    
    return query_str

def get_source_alias(station_code:str) -> str:
    '''
    handle USGS alias
    '''
    # TODO: update gmag.py in pyspedas to load themis and source aliases currently, takes THEMIS alias and corrects if source alias is different

    if station_code.lower() == "kevo":
        station_name_sourcealias = "kev"
    else:
        station_name_sourcealias = station_code
    return station_name_sourcealias

def get_usgs_variometer_avail(station_code:str,data_date:dt.datetime):
    print("Checking "+ station_code.upper() +" availability for date: " + data_date.strftime('%Y-%m-%d') + "...") 
    avail_netloc='service.earthscope.org' 
    avail_path='/fdsnws/availability/1/extent'
    # add channel at end:
    avail_query=[
        ('station',[get_source_alias(station_code).upper()]),
        ('start',[data_date.strftime('%Y-%m-%dT00:00:00')]),
        ('end',[data_date.strftime('%Y-%m-%dT23:59:59')])
    ]
    # construct URLs:
    query_list_bf1 = avail_query.copy()
    query_list_bf1.append(('channel',['BF1']))
    url1=construct_web_query(web_netloc=avail_netloc,web_path=avail_path,query_list=query_list_bf1)
    query_list_bf2 = avail_query.copy()
    query_list_bf2.append(('channel',['BF2']))
    url2=construct_web_query(web_netloc=avail_netloc,web_path=avail_path,query_list=query_list_bf2)
    query_list_bfz = avail_query.copy()
    query_list_bfz.append(('channel',['BFZ']))
    urlZ=construct_web_query(web_netloc=avail_netloc,web_path=avail_path,query_list=query_list_bfz)
    response_status_list = [
        urllib3.request("GET", url1).status,
        urllib3.request("GET", url2).status,
        urllib3.request("GET", urlZ).status
        ]
    if response_status_list != [200,200,200]:
        print("-> " + station_code.upper() + " data is NOT available for date: " + data_date.strftime('%Y-%m-%d') + ". Skipping..." )
        return False
    else:
        print("-> " + station_code.upper() + " data is available for date: " + data_date.strftime('%Y-%m-%d'))
        return True

def get_usgs_variometer_cal_history(station_code:str) -> str:
    print("Checking " + station_code.upper() + " latest calibration date...")
    cal_date_latest_str = ""
    url = construct_web_query(
        web_netloc='service.earthscope.org', # renamed from 'service.iris.edu'
        web_path='/irisws/metadatachange/1/query',
        query_list=[
            ('station',[get_source_alias(station_code).upper()]),
            ('format',['xml']),
            ('nodata',['404'])
            ]) # omitting ('channel','BF?'), for now, until earthscope fixes indexing issue
    # Attempt to make url request: 
    try:
        url_response_bytes = urllib3.request(
            "GET", 
            url, 
            retries=0,
            decode_content=False,
            preload_content=False,
            redirect=False,
            timeout=20)
        url_resp_str = decode2string(url_response_bytes)
    except urllib3.exceptions.TimeoutError:
        print("ERROR: Connection timed out! Calibration date could not be determined.")
        return ""
    else:
        # If we get a bad response, exit with an error status
        if url_response_bytes.status != 200:
            print("ERROR: Invalid status returned: " + str(url_response_bytes.status) + ". Calibration date could not be determined.")
            return ""
    
    root=ET.fromstring(url_resp_str)
    
    change_datetimes = []
    change_datetimes.append(str_list_max([change.attrib['changetime'] for change in root.findall(".//*[@code='BF1']..")]))
    change_datetimes.append(str_list_max([change.attrib['changetime'] for change in root.findall(".//*[@code='BF2']..")]))
    change_datetimes.append(str_list_max([change.attrib['changetime'] for change in root.findall(".//*[@code='BFZ']..")]))
    change_datetimes.append(str_list_max([change.attrib['changetime'] for change in root.findall("./*[@class='StationLocation']")]))
    
    cal_date_latest_str = str_list_max(change_datetimes)
    print("-> " + station_code.upper() + " data last calibrated on " + cal_date_latest_str)
    return cal_date_latest_str

def json2iaga2002(str_json_segment:str) -> str:
    '''
    A function to take a json of the data and convert it to an iaga2002 formatted string.

    Only a single start time should be provided, so the time series will need to be created from the start time and the sampling period
    '''
    NINES = numpy.float64("99999")
    json_segment = json.loads(str_json_segment)
    header_dict = {
        "Format":"IAGA-2002",
        "Source of Data":"United States Geological Survey (USGS)"
    }
    header_label_dict = {
        "name":"Station Name",
        "iaga_code":"IAGA CODE",
        "sensor_orientation":"Sensor Orientation",
        "data_type":"Data Type",
        "sampling_period":"Data Interval Type"
    }
    t_delta = dt.timedelta(seconds=1)
    for header_key in ["name","iaga_code","coordinates","sensor_orientation","data_type","sampling_period"]:
        json_header_dict = json_segment["metadata"]["intermagnet"]
        if header_key in ["name","iaga_code","coordinates"]:
            json_header_dict = json_header_dict["imo"]
        if header_key in json_header_dict:
            match header_key:
                case "coordinates":
                    header_dict["Geodetic Latitude"] = json_header_dict[header_key][1]
                    header_dict["Geodetic Longitude"] = json_header_dict[header_key][0]
                    header_dict["Elevation"] = json_header_dict[header_key][2]
                case "sensor_orientation":
                    if len(json_header_dict[header_key]) < 4:
                        header_dict["Reported"] = json_header_dict[header_key] + "NUL"
                    else:
                        header_dict["Reported"] = json_header_dict[header_key]
                    header_dict[header_label_dict[header_key]] = json_header_dict[header_key]
                case "sampling_period":
                    match str(json_header_dict[header_key]):
                        case "1.0":
                            header_dict[header_label_dict[header_key]] = "1-second"
                        case "0.1":
                            t_delta = dt.timedelta(milliseconds=100)
                case _:
                    header_dict[header_label_dict[header_key]] = json_header_dict[header_key]
    
    # Make header:
    header_str = ""
    for key_name in header_dict.keys():
        header_str += " " + key_name.ljust(23) + str(header_dict[key_name]).ljust(45) + "|" + "\n"
    if "Data Interval Type" in header_dict:
        header_str += " # Vector 1-second values are computed from 10 Hz values using a     |" + "\n"
        header_str += " # Blackman filter (123 taps, cutoff 0.25Hz) centered on the start   |" + "\n"
        header_str += " # of the second.                                                    |" + "\n"
        
    header_str += " # DISCLAIMER                                                        |" + "\n"
    header_str += " # This is provisional data. Any data secured from the USGS database |" + "\n"
    header_str += " # that are identified as provisional have not received Director's   |" + "\n"
    header_str += " # approval and are subject to revision. Source and Authority: U.S.  |" + "\n"
    header_str += " # Geological Survey Manual, Section 500.24                          |" + "\n"
    
    json_data = json_segment["values"]
    header_str += "DATE".ljust(11) + "TIME".ljust(13) + "DOY".ljust(8)
    header_str += (header_dict["IAGA CODE"] + json_data[0]["id"]).ljust(10)
    header_str += (header_dict["IAGA CODE"] + json_data[1]["id"]).ljust(10)
    header_str += (header_dict["IAGA CODE"] + json_data[2]["id"]).ljust(10)
    header_str += (header_dict["IAGA CODE"] + "NUL").ljust(7)
    header_str += "|"

    if len(json_data[0]["values"]) == len(json_data[1]["values"]) == len(json_data[2]["values"]):
        data_length = len(json_data[0]["values"])
    else: 
        data_length = max(len(json_data[0]["values"]),len(json_data[1]["values"]),len(json_data[2]["values"]))
        #raise ValueError("ERROR: Components have differing number of elements!","Component arrays had differing length")
        
    # initialize with start time:
    # format: 2025-11-17T00:00:00.069Z
    iaga_data_str = ""     
    row_datetime = dt.datetime.strptime(json_segment["times"][0], '%Y-%m-%dT%H:%M:%S.%fZ')
    iaga_data_arr = [" "] * data_length
    for i in range(data_length):
        iaga_data_row_str = ""
        # Date:
        iaga_data_row_str += row_datetime.strftime('%Y-%m-%d').ljust(11)
        # time:
        iaga_data_row_str += row_datetime.strftime('%H:%M:%S.%f')[:-3].ljust(13)
        # DOY
        iaga_data_row_str += row_datetime.strftime('%j').ljust(8)
        # component 1:
        for j in range(3):
            try:
                if type(json_data[j]["values"][i]).__name__ == "NoneType": 
                    raise ValueError("ERROR: JSON is missing data!","Segment was missing data.")
                iaga_data_row_str += ("%.2f" % json_data[j]["values"][i]).ljust(10)
            except IndexError:
                iaga_data_row_str += ("%.2f" % NINES).ljust(10)
        # component nul:
        iaga_data_row_str += ("%.2f" % NINES).ljust(7)
        
        # Assign value in array to line:
        iaga_data_arr[i] = iaga_data_row_str
        # increment time by sampling rate:
        row_datetime = row_datetime + t_delta
    iaga_data_str = "\n".join(iaga_data_arr)
    
    iaga_arr = [header_str,iaga_data_str]
    iaga_str = "\n".join(iaga_arr) + "\n"
    
    return iaga_str

def decode2string(bytes_response):
    '''
    take in a urllib3 response object as bytes and decode to utf-8 function is separate from others so concurrent module can run decode calls in parallel
    '''
    try:
        #bytes_response_read = bytes_response.read()
        # we should be able to safely close the original url responses:
        #bytes_response.close()
        string_response=bytes_response.data.decode('utf-8') #bytes_response_read.decode('utf-8')
        bytes_response.close()
        if string_response == '': 
            raise ValueError(
                "ERROR! Decoded bytes_response is empty!",
                "Empty response")
        else:
            return string_response
    except urllib3.exceptions.IncompleteRead:
        raise ValueError(
            "ERROR! Incomplete file due to timed out connection!",
            "Connection timed out during retrieval")
    except urllib3.exceptions.ProtocolError:
        raise ValueError(
            "ERROR! Incomplete file due to timed out connection!",
            "Connection timed out during retrieval")    

def decode_and_convert(bytes_response) -> str:
    str_response = decode2string(bytes_response)
    output_string = json2iaga2002(str_response)
    return output_string

def correct_start_time(
        station_code:str,
        start_datetime:dt.datetime,
        sampling_period:str,
        recursive_run:bool=False) -> dt.datetime:
    '''
    Makes a quick USGS iaga2002 query for a very short timespan, and checks status
    if the status returned is 500, slightly adjust start time and try again 
    '''
    url=construct_usgs_query(
        station_code=station_code,
        start_datetime=start_datetime,
        end_datetime=start_datetime + dt.timedelta(seconds=1),
        data_format = 'iaga2002',
        sampling_period=sampling_period)
    http_1 = urllib3.PoolManager(num_pools=24) # num_pools=10
    retries_settings=urllib3.Retry(
        connect=0,
        read=2,
        backoff_factor=0.5)
    url_response_bytes = http_1.request(
        "GET", 
        url, 
        retries=retries_settings,
        decode_content=False,
        preload_content=False,
        redirect=False,
        timeout=30)
    url_response_status = url_response_bytes.status
    url_response_bytes.close()
    match url_response_status:
        case 200:
            return start_datetime
        case 500:
            if recursive_run: 
                raise ValueError(
                    "ERROR! Remote source encountered internal server error.",
                    "Remote source internal server error")
            else:
                print("WARNING: Possible component array mismatch detected; modifying query to attempt correction.")
                modified_start_time = correct_start_time(
                    station_code=station_code,
                    start_datetime=start_datetime - dt.timedelta(milliseconds=99),
                    sampling_period=sampling_period,
                    recursive_run=True)
                return modified_start_time
        case _:
            raise ValueError(
                "ERROR: Invalid status returned: " + str(url_response_bytes.status) + ".",
                "Bad response status code: " + str(url_response_bytes.status)) 

def retrieve_file_bytes(
        station_code:str,
        start_datetime:dt.datetime,
        end_datetime:dt.datetime,
        sampling_period:str,
        max_num_retries:int,
        correct_time=True) -> urllib3.response.BaseHTTPResponse:
    try:
        # use parameters to construct query, make request:
        #if sampling_period == "0.1" and correct_time:
        #    corrected_time_start = dt.datetime.now()
        #    start_datetime = correct_start_time(
        #        station_code=station_code,
        #        start_datetime=start_datetime,
        #        sampling_period=sampling_period)
        url=construct_usgs_query(
            station_code=station_code,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            sampling_period=sampling_period)
        # Attempt to make url request: 
        http = urllib3.PoolManager(num_pools=24) # num_pools=10
        retries_settings=urllib3.Retry(
            connect=0,
            read=max_num_retries,
            backoff_factor=0.5)
        url_response_bytes = http.request(
            "GET", 
            url, 
            retries=retries_settings,
            decode_content=False,
            preload_content=False,
            redirect=False,
            timeout=30)
        match url_response_bytes.status:
            case 200:
                if b"HTTP/1.1 408 Request Timeout" in url_response_bytes.data:
                    if max_num_retries > 0:
                        print("Request timeout detected within response data. Attempting again")
                        url_response_bytes_retry = retrieve_file_bytes(
                            station_code=station_code,
                            start_datetime=start_datetime,
                            end_datetime=end_datetime,
                            sampling_period=sampling_period,
                            max_num_retries=max_num_retries-1,
                            correct_time=False)
                        return url_response_bytes_retry
                    else:
                        raise ValueError(
                            "ERROR! Incomplete file due to timed out connection!",
                            "Connection timed out during retrieval")
                elif len(url_response_bytes.data) == 0:
                    if max_num_retries > 0:
                        print("Request returned empty; Attempting again...")
                        url_response_bytes_retry = retrieve_file_bytes(
                            station_code=station_code,
                            start_datetime=start_datetime,
                            end_datetime=end_datetime,
                            sampling_period=sampling_period,
                            max_num_retries=max_num_retries-1,
                            correct_time=False)
                        return url_response_bytes_retry
                    else:
                        raise ValueError(
                            "ERROR! Decoded bytes_response is empty!",
                            "Empty response")
                else:
                    return url_response_bytes
            case _:
                raise ValueError(
                    "ERROR: Invalid status returned: " + str(url_response_bytes.status) + ".",
                    "Bad response status code: " + str(url_response_bytes.status)) 
    except urllib3.exceptions.TimeoutError:
        raise ValueError(
            "ERROR: Connection timed out!",
            "Connection timed out during retrieval")
    except urllib3.exceptions.MaxRetryError:
        raise ValueError(
            "ERROR: Connection could not be established after " + str(max_num_retries + 1) + " attempt(s)",
            "Max connection retry limit reached")

def retrieve_a_file(
        station_code:str,
        data_date:dt.datetime,
        variometer_workdir:Path,
        mirror_dir=None,
        sampling_rate:str='1',
        max_num_retries:int=0) -> dict:
    out_dict = {"LastAttemptedAccessTime":"","LastSuccessfulAccessTime":"","error_status":""}
    try:
        # use sampling_rate arg to define additional retrieval parameters
        match sampling_rate:
            case '1':
                sampling_period_val='1'
                workdir_subdir = Path(f"{variometer_workdir}/{sampling_rate}_hz")
                Path(workdir_subdir).mkdir(parents=True, exist_ok=True)
                output_filepath_list = [Path(f"{workdir_subdir}/{station_code.lower()}{data_date.strftime('%Y%m%d')}vsec.sec")]
                if mirror_dir is not None:
                    mirror_subdir = Path(f"{mirror_dir}/{station_code.lower()}/1_hz/{data_date.strftime('%Y')}/{data_date.strftime('%m')}")
                    mirror_subdir.mkdir(parents=True, exist_ok=True)
                    output_filepath_list.append(Path(f"{mirror_subdir}/{station_code.lower()}{data_date.strftime('%Y%m%d')}vsec.sec"))
                duration=6 # duration of each segment, in hours # formerly 24
                #segment_end_str = "000"
                sampling_rate_td = dt.timedelta(seconds=1)
            case '10':
                sampling_period_val='0.1'
                workdir_subdir = Path(f"{variometer_workdir}/{sampling_rate}_hz")
                Path(workdir_subdir).mkdir(parents=True, exist_ok=True)
                output_filepath_list = [Path(f"{workdir_subdir}/{station_code.lower()}{data_date.strftime('%Y%m%d')}vdec.dec")]
                duration=1 # duration of each segment, in hours # formerly 4
                #segment_end_str = "000" # was 999
                sampling_rate_td = dt.timedelta(milliseconds=100)
            case _:
                raise ValueError("ERROR: Sampling rate not recognized","Invalid Sampling Rate")
        
        print("Retrieving " + station_code.upper() + " data for "+ data_date.strftime('%Y-%m-%d') +" in " + str(round(24/duration)) + " segments... ")
        start_time_1file = dt.datetime.now()
        out_dict["LastAttemptedAccessTime"] = dt.datetime.strftime(start_time_1file,'%Y-%m-%d %H:%M:%S')

        # make requests to USGS server and collect response objects in a list: 
        url_response_bytes_list = []
        date_start_dt = dt.datetime.strptime(data_date.strftime('%Y-%m-%d') + "T" + "00:00:00.000Z", '%Y-%m-%dT%H:%M:%S.%fZ')
        for start_hour in range(0, 24, duration):
            segment_start_time_1file = dt.datetime.now()
            segment_name_str = str(round((start_hour+duration)/duration)) + "/"+str(round(24/duration))
            #print("-> Retrieving segment "+ str(round((start_hour+duration)/duration)) + "/"+str(round(24/duration))+"...")
            # start hour increases by length of duration
            segment_start_dt = date_start_dt + dt.timedelta(hours = start_hour)
            # end time is one segment duration after start time, but subtract sampling rate so times do not overlap:
            segment_end_dt = segment_start_dt + dt.timedelta(hours = duration) - sampling_rate_td
            url_response_bytes = retrieve_file_bytes(
                station_code=station_code,
                start_datetime=segment_start_dt,
                end_datetime=segment_end_dt,
                sampling_period=sampling_period_val,
                max_num_retries=max_num_retries)
            print("-> Retrieval of segment "+ segment_name_str +" complete. Elapsed %.0f seconds." % (dt.datetime.now() - segment_start_time_1file).seconds)
            url_response_bytes_list.append(url_response_bytes)
        # Take list of byte responses and decode:
        decoding_start_time = dt.datetime.now()
        print("Download of all segments complete. Elapsed %.0f seconds." % (decoding_start_time - start_time_1file).seconds)
        output_string_list = []
        with futures.ThreadPoolExecutor(round(24/duration)) as executor:
            output_string_list = executor.map(decode_and_convert, url_response_bytes_list)
        output_string_list=list(output_string_list)
        # File strings should be complete and correct. Write strings to file:    
        writing_start_time = dt.datetime.now()
        print("Decoding and conversion complete. Elapsed %.0f seconds." % (writing_start_time - decoding_start_time).seconds)
        out_dict["LastSuccessfulAccessTime"] = dt.datetime.strftime(start_time_1file,'%Y-%m-%d %H:%M:%S')
        # If output file path already exists, delete it and create a new one:
        for output_filepath in output_filepath_list:    
            output_filepath.unlink(missing_ok=True)
            output_file = open(output_filepath, "x")
            output_file.close()
            # For each url response string, append to new file. Only keep the header for the first string:
            for output_string_list_list_idx in range(len(output_string_list)):
                output_string = output_string_list[output_string_list_list_idx]
                # if the url response string comes first in the list, keep the header; otherwise, remove lines containing the | character followed by a newline:
                if output_string_list_list_idx == 0:
                    string_towrite = output_string
                else:
                    string_towrite = re.sub(r".*\|\n", "", output_string)
                with open(output_filepath, "a") as of:
                    of.write(string_towrite)   
        end_time_1file = dt.datetime.now()
        print("File writing complete. Elapsed %.0f seconds." % (end_time_1file - writing_start_time).seconds)
        print("Total file retrieval complete. Elapsed time: %.0f seconds." % (end_time_1file - start_time_1file).seconds)
    except ValueError as error:
        print(error.args[0] + " File could not be written; Aborting file retrieval...")
        out_dict["error_status"] = error.args[1]
    #except:
    #    print("ERROR! The output file could not be written.")
    #    out_dict["error_status"] = "Failed to write data to output file."
    return out_dict

def run_gmag_retrieve_usgs_variometer(
        station_list:list[str], 
        start_date=None, 
        end_date=None, 
        days=None, 
        output_p_str:str="",
        issue_list_fp_str:str="", 
        db_update_fp_str:str="", 
        sampling_rate:str = '1', 
        max_num_retries:int=0) -> int:
    main_start_time = dt.datetime.now()
    str_datetime_run = main_start_time.strftime('%Y%m%d_%H%M%S')  

    thmsoc_python_root = Path(__file__).resolve().parent.parent.parent
    thmsoc_python_config = thmsoc_python_root / "thmsoc_python_config.toml"
    try:
        with open(thmsoc_python_config, "rb") as f:
            toml_dict = tomli.load(f)
            OUTDATAROOT = Path(toml_dict["paths"]["output_dataroot"])
    except FileNotFoundError:
        OUTDATAROOT = Path("/disks/themisdata")
    
    # Set variometer_workdir as output directory has been passed; otherwise use default. Additionally, add mirror directory if the sample rate is 1:
    variometer_workdir = Path(f"{OUTDATAROOT}/workdir/usgs_variometer2do")
    variometer_mirrordir = None
    if output_p_str != "":
        variometer_workdir = Path(f"{output_p_str}")
    else:
        if sampling_rate == '1':
            variometer_mirrordir = Path(f"{OUTDATAROOT}/thg/mirrors/variometers/usgs_ascii")
            variometer_mirrordir.mkdir(parents=True, exist_ok=True)
    # shouldn't need to make workdir in practice, but including here to be safe:
    variometer_workdir.mkdir(parents=True, exist_ok=True)
    
    # Set sql filepath to database update sql file has not been set, create one:
    if db_update_fp_str != "":
        fp_db_update = Path(f"{db_update_fp_str}")
    else:    
        mysql_workdir = Path(f"{OUTDATAROOT}/workdir/mysql_db_queries")
        mysql_workdir.mkdir(parents=True, exist_ok=True)
        fp_db_update = Path(f"{mysql_workdir}/gmag_retrieve_usgs_variometers_{str_datetime_run}.sql")
    
    # If filepath to database update sql file already exists, delete it and create a new one:
    fp_db_update.unlink(missing_ok=True)
    sqldbf = open(fp_db_update, "x")
    sqldbf.close()
    db_table = "usgs_" + sampling_rate + "_hz_retrieval_processing_history"
    
    # Parse arguments to get start and end datetime values:
    dt_start,dt_end = args_to_startend(start_date, end_date, days)
    
    # Get latest calibration date for each station in station list: 
    cal_check_start_time = dt.datetime.now()
    print("------ Checking latest calibration dates... ------")
    cal_date_dict = dict()
    for station_code in station_list:
        cal_date_dict[station_code] = get_usgs_variometer_cal_history(station_code)
    print("Calibration date checking complete. Elapsed a total of %.0f seconds." % (dt.datetime.now() - cal_check_start_time).seconds )
    
    print("------ Beginning File Retrieval... ------")
    missing_file_list = ""
    # Retrieve files for specified stations for each date in date range: 
    for date_batch in batch_daterange(dt_start, dt_end, days_per_batch=1):
        current_date = date_batch[0]
        # Retrieve files for each station at this current date:
        for station_code in station_list:
            print("--- Attempting to retrieve "+ station_code.upper() + " data for " + current_date.strftime('%Y-%m-%d') + " at sampling rate: " + sampling_rate + " Hz ---")
            # Initialize dictionary containing results of attempted retrieval for given station and date:
            result_dict = {"LastAttemptedAccessTime":"","LastSuccessfulAccessTime":"","error_status":""}
            # If file is available, for given station and date, attempt to retrieve it:
            if get_usgs_variometer_avail(station_code,current_date):
                result_dict = retrieve_a_file(
                    station_code=station_code,
                    data_date=current_date,
                    variometer_workdir=variometer_workdir,
                    mirror_dir=variometer_mirrordir,
                    sampling_rate=sampling_rate,
                    max_num_retries=max_num_retries)
            result_dict["site"] = station_code
            result_dict["DataDate"] = current_date.strftime('%Y-%m-%d')
            if result_dict["LastSuccessfulAccessTime"] != "":
                result_dict["CalibrationTime"] = cal_date_dict[station_code]
            # Take result dictionary, create sql insert update query from it, and append query line to sql query file:
            with open(fp_db_update, "a") as of:
                print(sql_insert_update_query(db_table=db_table, in_dict=result_dict), file=of)
                #of.write(sql_insert_update_query(db_table=db_table, in_dict=result_dict))
            if result_dict["error_status"] != "":
                missing_file_list += "Station: " + (station_code.upper() + ",").ljust(5) + " Date: "+ current_date.strftime('%Y-%m-%d') +", Issue: " + result_dict["error_status"] + "\n"
    print("------ Script complete. Elapsed %.0f seconds ------" % (dt.datetime.now() - main_start_time).seconds)
    if missing_file_list != "":
        print("Retrieval was attempted for the following files, but failed for the following reasons: ")
        print(missing_file_list)
        # Make directory if it doesn't exist:
        failed_list_p = Path(f"{OUTDATAROOT}/process_logs/gmag/webdownloads/variometers/usgs/{sampling_rate}_hz")
        if issue_list_fp_str != "":
            failed_list_fp = Path(f"{issue_list_fp_str}")
        else:
            failed_list_p.mkdir(parents=True, exist_ok=True)
            failed_list_fp = Path(f"{failed_list_p}/failed_list{str_datetime_run}.txt")
        # Create file and print missing file list to file:
        failed_list_fp.unlink(missing_ok=True)
        failedf = open(failed_list_fp, "x")
        failedf.close()
        with open(failed_list_fp, "a") as of:
            print(missing_file_list, file=of)
        return 1
    else:      
        return 0

if __name__ == "__main__":
    run_gmag_retrieve_usgs_variometer(start_date="2025-11-17",end_date="2025-11-17", station_list=['s61a'],sampling_rate='10')