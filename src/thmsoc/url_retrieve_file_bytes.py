import urllib3
from pathlib import Path
from urllib.request import urlretrieve

def retrieve_file_bytes(
        url:str,
        max_num_retries:int=0,
        timeout_content:bytes|None=None,
        **request_kwargs) -> urllib3.response.BaseHTTPResponse:
    try:
        # Attempt to make url request: 
        http = urllib3.PoolManager(num_pools=24) # num_pools=10
        retries_settings=urllib3.Retry(
            total=max_num_retries,
            connect=0,
            read=max_num_retries,
            backoff_factor=0.5)
        request_args = {
            "url":url,
            "retries":retries_settings,
            "decode_content":False,
            "preload_content":False,
            "redirect":False,
            "timeout":30
        }
        request_args.update(request_kwargs)
        url_response_bytes = http.request(
            "GET", 
            **request_args)
        match url_response_bytes.status:
            case 200:
                if url_response_bytes.retries is not None and url_response_bytes.retries.total is not None:
                    if timeout_content is not None and timeout_content in url_response_bytes.data:
                        if url_response_bytes.retries.total <= max_num_retries:    
                            print("Request timeout detected within response data; Attempting again...")
                            url_response_bytes_retry = retrieve_file_bytes(
                                url=url,
                                max_num_retries=max_num_retries-1,
                                timeout_content=timeout_content)
                            return url_response_bytes_retry
                        else:
                            raise ValueError(
                                "ERROR! Incomplete file due to timed out connection!",
                                "Connection timed out during retrieval")
                    elif len(url_response_bytes.data) == 0:
                        if url_response_bytes.retries.total <= max_num_retries:    
                            print("Request returned empty; Attempting again...")
                            url_response_bytes_retry = retrieve_file_bytes(
                                url=url,
                                max_num_retries=max_num_retries-1,
                                timeout_content=timeout_content)
                            return url_response_bytes_retry
                        else:
                            raise ValueError(
                                "ERROR! Decoded bytes_response is empty!",
                                "Empty response")
                    else:
                        return url_response_bytes
                else:
                    raise ValueError(
                        "ERROR: Invalid response returned; does not contain retries attribute.",
                        "URL response lacked retries attribute.")
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

def retrieve_file_from_url(url,out_filename:Path | None = None,format:str | None=None,**retrieve_file_bytes_kwargs):
    """
    Retrieve contents of URL in specified format. If out_filename path is provided, write contents of URL to file.
    """
    url_response = ""
    match format:
        case "bytes":
            url_response = retrieve_file_bytes(**retrieve_file_bytes_kwargs)
        case _:
            if out_filename is not None:
                url_response = (urlretrieve(url,str(out_filename)))[1]
            else:
                url_response = (urlretrieve(url))[1]
    return url_response

if __name__ == "__main__":
    bytes_response = retrieve_file_bytes(
        url=("https://geomag.usgs.gov/ws/algorithms/filter/?"
        "elements=X&elements=Y&elements=Z&format=iaga2002&id=J47A&type=variation"
        "&starttime=2026-06-29T00:00:00.000Z&endtime=2026-06-29T03:00:00.000Z"
        "&output_sampling_period=0.1"),
        max_num_retries=0,
        timeout_content=b"HTTP/1.1 408 Request Timeout") # timeout=3