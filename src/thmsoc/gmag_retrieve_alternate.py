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



def retrieve_alt_file(scode:str, date:dt.datetime, tmp_root:Path=Path("")):
    # determine which retrieval method to use from the station code
    # TODO: this could use pyspedas gmag to get the gmag metadata to find group name
    group_str = ""
    waveform_kwargs={}
    if scode.lower()=="snkq":
        group_str = "nrcan"
        waveform_kwargs = {
            "station":"SNK",
            "network":'C2',
            "location":'R1',
            "channel":'UFX,UFY,UFZ,UFF'
        }

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
                endtime=UTCDateTime((date + dt.timedelta(days = 1)).strftime('%Y-%m-%dT00:00:00.000')))
            
            channel_list = [substring.strip() for substring in waveform_kwargs["channel"].split(",")]
            
            f_raw_list = []
            for cha in channel_list:
                f_raw = Path(f"{proc_dir}/{scode.upper()}{date.strftime('%Y%m%d')}_{cha}.txt")
                tmp = st.select(channel=cha,**{x: waveform_kwargs[x] for x in waveform_kwargs if x != "channel"}) 
                tmp.merge(fill_value=np.nan)
                tmp.write(str(f_raw),format = "TSPAIR")
                f_raw_list.append(f_raw)

            # for each file name in f_raw_list, parse text file into iaga2002 format
            

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