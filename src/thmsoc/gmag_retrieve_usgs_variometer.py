# src/thmsoc/gmag_retrieve_usgs_variometer.py
import datetime as dt
import urllib3
from pathlib import Path
import tomli
import re
from thmsoc import args_to_startend, batch_daterange
from concurrent import futures
import xml.etree.ElementTree as ET

def list_max(in_list:list):
    list_unique = list(dict.fromkeys(in_list))
    list_unique.sort()
    return list_unique[-1]

# take in a urllib3 response object as bytes and decode to utf-8 function is separate from others so concurrent module can run decode calls in parallel
def decode2string(bytes_response):
    # TODO: create some kind of setting which can be updated to choose incomplete and protocol error responses. 
    try:
        bytes_response_read = bytes_response.read()
    except urllib3.exceptions.IncompleteRead:
        # kluge since http.client.IncompleteRead has been thrown in process of handling exception:
        try: 
            return 'HTTP/1.1 408 Request Timeout'
        except urllib3.exceptions.IncompleteRead:
            #print("ERROR: Connection timed out! Aborting file retrieval...")
            return 'HTTP/1.1 408 Request Timeout'
    except urllib3.exceptions.ProtocolError:
        #print("ERROR: Connection timed out! Aborting file retrieval...")
        return 'HTTP/1.1 408 Request Timeout'
    else:
        string_response=bytes_response_read.decode('utf-8')
        return string_response

def construct_web_query(
        web_scheme='https',
        web_netloc='',
        web_path='',
        query_list:list=[],
        query_separator='&',
        web_fragment=''
        ):
    # construct_web_query assumes query_list is an iterable, where each element is a tuple containing the query parameter name and an iterable with one or more elements, which will be populated into the query individually
    web_query=''
    if len(query_list) > 0:
        web_query += "?"
        for query_idx in range(len(query_list)):
            query_name,values = query_list[query_idx]
            for value_idx in range(len(values)):
                if value_idx == 0:
                    web_query += query_name + '=' + values[value_idx]
                else:
                    web_query += query_separator + query_name + '=' + values[value_idx]
            if query_idx+1 < len(query_list):
                web_query+=query_separator    
    return web_scheme+"://"+web_netloc+web_path+web_query+web_fragment

# construct URLs which query USGS server
# TODO: generalize script, maybe add to separate thmsoc URL handling script?
def construct_usgs_query(
        station_code, 
        start_datetime: dt.datetime, 
        end_datetime: dt.datetime, 
        sampling_period, 
        elements_list=['X','Y','Z'],
        usgs_remote_source_path='/ws/algorithms/filter/'
        ):
    usgs_netloc='geomag.usgs.gov'
    usgs_path=usgs_remote_source_path
    usgs_query_list=[
        ('elements',elements_list),
        ('format',['iaga2002']),
        ('id',[get_source_alias(station_code).upper()]),
        ('type',['variation']),
        ('starttime',[start_datetime.strftime('%Y-%m-%dT%H:%M:%S.%fZ')]),
        ('endtime',[end_datetime.strftime('%Y-%m-%dT%H:%M:%S.%fZ')]),
        ('output_sampling_period',[sampling_period])
    ]
    return construct_web_query(web_netloc=usgs_netloc,web_path=usgs_path,query_list=usgs_query_list)

# create an sql update query from dict containing fields and associated values
def sql_insert_update_query(db_table:str, in_dict:dict) -> str:
    query_str = 'INSERT INTO '
    query_str += db_table + '(site,DataDate,'
    query_values_str = in_dict["site"] + ',"' + in_dict["DataDate"] + '",'
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

# handle USGS alias
# TODO: update gmag.py in pyspedas to load themis and source aliases
# currently, takes THEMIS alias and corrects if source alias is different
def get_source_alias(station_code:str) -> str:
    if station_code.lower() == "kevo":
        station_name_sourcealias = "kev"
    else:
        station_name_sourcealias = station_code
    return station_name_sourcealias

def get_usgs_variometer_avail(station_code:str,data_date:dt.datetime):
    print("Checking "+ station_code.upper() +" availability for date: " + data_date.strftime('%Y-%m-%d') + "...") 
    #avail_netloc='service.iris.edu' 
    # Setting network location to earthscope since iris should be getting discontinued:
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
    #if 404 in response_status_list:
    #    print(station_code.upper() + " data is NOT available for the date " + data_date.strftime('%Y-%m-%d'))
    #    return False
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
    
    #url_resp = urllib3.request("GET", url)
    root=ET.fromstring(url_resp_str)
    #root=ET.fromstring(url_response_bytes.data)
    
    change_datetimes = []
    change_datetimes.append(list_max([change.attrib['changetime'] for change in root.findall(".//*[@code='BF1']..")]))
    change_datetimes.append(list_max([change.attrib['changetime'] for change in root.findall(".//*[@code='BF2']..")]))
    change_datetimes.append(list_max([change.attrib['changetime'] for change in root.findall(".//*[@code='BFZ']..")]))
    change_datetimes.append(list_max([change.attrib['changetime'] for change in root.findall("./*[@class='StationLocation']")]))
    
    cal_date_latest_str = list_max(change_datetimes)
    print("-> " + station_code.upper() + " data last calibrated on " + cal_date_latest_str)
    return cal_date_latest_str

def retrieve_a_file(
        station_code:str,
        data_date:dt.datetime,
        variometer_workdir:Path,
        mirror_dir=None,
        sampling_rate:str='1',
        max_num_retries:int=0) -> dict:
    out_dict = {"LastAttemptedAccessTime":"","LastSuccessfulAccessTime":"","error_status":""}
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
            duration=24 # duration of each segment, in hours
        case '10':
            sampling_period_val='0.1'
            workdir_subdir = Path(f"{variometer_workdir}/{sampling_rate}_hz")
            Path(workdir_subdir).mkdir(parents=True, exist_ok=True)
            output_filepath_list = [Path(f"{workdir_subdir}/{station_code.lower()}{data_date.strftime('%Y%m%d')}vdec.dec")]
            duration=4 # duration of each segment, in hours
        case _:
            print("ERROR: Sampling rate not recognized")
            out_dict["error_status"] = "Invalid Sampling Rate"
            return out_dict
    
    print("Retrieving " + station_code.upper() + " data for "+ data_date.strftime('%Y-%m-%d') +" in " + str(round(24/duration)) + " segments... ")
    start_time_1file = dt.datetime.now()
    out_dict["LastAttemptedAccessTime"] = dt.datetime.strftime(start_time_1file,'%Y-%m-%d %H:%M:%S')
    # make requests to USGS server and collect response objects in a list: 
    url_response_bytes_list = []
    # start hour increases by length of duration
    for start_hour in range(0, 24, duration):
        segment_start_time_1file = dt.datetime.now()
        # end time will be 0.001 second before next segment start time:
        end_hour = start_hour + duration - 1
        data_date_str = data_date.strftime('%Y-%m-%d')
        start_datetime_val=dt.datetime.strptime(data_date_str + "T" + str(start_hour) + ":00:00.000Z", '%Y-%m-%dT%H:%M:%S.%fZ')
        end_datetime_val=dt.datetime.strptime(data_date_str + "T" + str(end_hour) + ":59:59.999Z", '%Y-%m-%dT%H:%M:%S.%fZ')

        # use parameters to construct query, make request:
        url=construct_usgs_query(station_code=station_code,start_datetime=start_datetime_val,end_datetime=end_datetime_val,sampling_period=sampling_period_val)
        
        # Attempt to make url request: 
        http = urllib3.PoolManager(num_pools=10)
        try:
            url_response_bytes = http.request(
                "GET", 
                url, 
                retries=max_num_retries,
                decode_content=False,
                preload_content=False,
                redirect=False,
                timeout=20)
        except urllib3.exceptions.TimeoutError:
            print("ERROR: Connection timed out! Aborting file retrieval... ---")
            out_dict["error_status"] = "Connection timed out"
            return out_dict
        except urllib3.exceptions.MaxRetryError:
            print("ERROR: Connection could not be established after " + str(max_num_retries + 1) + " attempt(s); Aborting file retrieval... ---")
            out_dict["error_status"] = "Max connection retry limit reached"
            return out_dict
        else:
            # If we get a bad response, exit with an error status
            if url_response_bytes.status == 200:
                # If we received a good response, append to list of responses
                print("-> Segment "+ str(round((start_hour+duration)/duration)) + "/"+str(round(24/duration))+" retrieval complete. Elapsed %.0f seconds." % (dt.datetime.now() - segment_start_time_1file).seconds)
                url_response_bytes_list.append(url_response_bytes)
            else:
                print("ERROR! Invalid status returned: " + str(url_response_bytes.status) + "; Aborting file retrieval... ---")
                out_dict["error_status"] = "Connection returned status: " + str(url_response_bytes.status)
                return out_dict
    
    # Take list of byte responses and decode:
    decoding_start_time = dt.datetime.now()
    print("Download of all segments complete. Elapsed %.0f seconds." % (decoding_start_time - start_time_1file).seconds)
    url_response_string_list=[]
    # using the ThreadPoolExecutor object, map input url_response_bytes_list to output url_response_string_list, running on 24/duration threads (should be 6 for 10 Hz, 1 for 1 Hz)
    with futures.ThreadPoolExecutor(round(24/duration)) as executor:
        url_response_string_list = executor.map(decode2string, url_response_bytes_list)
    url_response_string_list=list(url_response_string_list)

    # we should be able to safely close the original url responses:
    for url_response_bytes in url_response_bytes_list:
        #http.releaseconn()
        url_response_bytes.close()

    # verify that the output strings aren't empty or contain timeout signatures. if they do, exit with error status
    verification_start_time=dt.datetime.now()
    print("Decoding complete. Elapsed %.0f seconds." % (verification_start_time - decoding_start_time).seconds)
    # loop once, check for timeout strings:
    for url_response_string in url_response_string_list:
        # check for timeout contents, abandon process if detected.
        if url_response_string == '':
            print("ERROR! Incomplete file due to empty segment! File could not be written; Aborting file retrieval... ")
            out_dict["error_status"] = "At least one of the segments was empty"
            return out_dict
        elif "HTTP/1.1 408 Request Timeout" in url_response_string:
            print("ERROR! Incomplete file due to timed out connection! File could not be written; Aborting file retrieval... ")
            out_dict["error_status"] = "Connection timed out during retrieval"
            return out_dict

    # File strings should be complete and correct. Write strings to file:    
    writing_start_time = dt.datetime.now()
    print("File verification complete. Elapsed %.0f seconds." % (writing_start_time - verification_start_time).seconds)
    out_dict["LastSuccessfulAccessTime"] = dt.datetime.strftime(start_time_1file,'%Y-%m-%d %H:%M:%S')
    
    # If output file path already exists, delete it and create a new one:
    for output_filepath in output_filepath_list:    
        try:
            output_filepath.unlink(missing_ok=True)
            output_file = open(output_filepath, "x")
            output_file.close()
            # For each url response string, append to new file. Only keep the header for the first string:
            for url_response_string_list_idx in range(len(url_response_string_list)):
                url_response_string = url_response_string_list[url_response_string_list_idx]    
                # if the url response string comes first in the list, keep the header; otherwise, remove lines containing the | character followed by a newline:
                if url_response_string_list_idx == 0:
                    string_towrite = url_response_string
                else:
                    string_towrite = re.sub(r".*\|\n", "", url_response_string)
                with open(output_filepath, "a") as of:
                    of.write(string_towrite)
            end_time_1file = dt.datetime.now()
            print("File writing complete. Elapsed %.0f seconds." % (end_time_1file - writing_start_time).seconds)
            print("Total file retrieval complete. Elapsed time: %.0f seconds." % (end_time_1file - start_time_1file).seconds)            
        except:
            print("ERROR! The output file could not be written: " + str(output_filepath))
            out_dict["error_status"] = "Failed to write data to output file."
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
    print("--- Checking latest calibration dates... ---")
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
            print("--- Attempting to retrieve "+ station_code.upper() + " data for " + current_date.strftime('%Y-%m-%d') + " at sampling rate: " + sampling_rate + "Hz ---")
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
                missing_file_list += "Station: " + station_code.upper() + ", Date: "+ current_date.strftime('%Y-%m-%d') +", Issue: " + result_dict["error_status"] + "\n"
    print("--- Script complete. Elapsed %.0f seconds ---" % (dt.datetime.now() - main_start_time).seconds)
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
    