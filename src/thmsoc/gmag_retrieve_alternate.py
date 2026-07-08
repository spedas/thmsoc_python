"""
gmag_retrieve_alternate

retrieves GMAG data from alternate sources to supplement AE index calculation
"""
import datetime as dt
from thmsoc.url_construct_web_query import url_construct_web_query
from pathlib import Path
import tomli
import obspy
import numpy as np

def miniseedtxt2iaga2002(comp_list:list=[]):
    """
    Create iaga2002 formatted text file from miniseed component file(s), currently assumed to be GMAG B field vector variation measurements
    """
    return

def retrieve_miniseed(scode:str,date:dt.datetime,proc_dir:Path=Path(""),obspy_select_kwargs:dict={},out_format:str="iaga2002"):
    start_datetime_str = date.strftime('%Y-%m-%dT00:00:00Z')
    end_datetime_str = (date + dt.timedelta(days = 1)).strftime('%Y-%m-%dT00:00:00Z')

    url = url_construct_web_query(
        web_scheme='http',
        web_netloc='www.earthquakescanada.nrcan.gc.ca',
        web_path='/fdsnws/dataselect/1/query/',
        query_list=[
            ('station',scode),
            ('starttime',start_datetime_str),
            ('endtime',end_datetime_str)
        ],
        query_separator='&',
        web_fragment='')
    
    # Download miniseed data file to working directory
    fn = Path(f"{proc_dir}/{scode.upper()}{date.strftime('%Y%m%d')}.mseed")
    # read miniseed file using obspy:

    st = obspy.read(str(fn))

    f_raw_list = []
    if type(obspy_select_kwargs.get("channel")) == list:
        for cha in obspy_select_kwargs["channel"]:
            f_raw = Path(f"{proc_dir}/{scode.upper()}{date.strftime('%Y%m%d')}_{cha}.txt")
            tmp = st.select(
                channel=cha,
                **{x: obspy_select_kwargs[x] for x in obspy_select_kwargs if x != "channel"}
                ) 
            tmp.merge(fill_value=np.nan)
            tmp.write(str(f_raw),format = "TSPAIR")
            f_raw_list.append(f_raw)
    else:
        f_raw = Path(f"{proc_dir}/{scode.upper()}{date.strftime('%Y%m%d')}.txt")
        tmp = st.select(**obspy_select_kwargs) 
        tmp.merge(fill_value=np.nan)
        tmp.write(str(f_raw),format = "TSPAIR")
        f_raw_list.append(f_raw)

    # for each file name in f_raw_list, parse text file

    match out_format:
        case "iaga2002":
            miniseedtxt2iaga2002(comp_list=f_raw_list)
    return

def retrieve_alt_file(scode:str, date:dt.datetime, tmp_root:Path=Path("")):
    # determine which retrieval method to use from the station code
    # TODO: this could use pyspedas gmag to get the gmag metadata to find group name
    group_str = ""
    scode_alias = ""
    if scode.lower()=="snkq":
        group_str = "nrcan"
        scode_alias = "SNK"
        obspy_select_kwargs = {
            "network":'C2',
            "location":'R1',
            "channel":['UFX','UFY','UFZ','UFF']
        }

    proc_dir = Path(f"{tmp_root}/retrieve_alternate/{group_str}")
    proc_dir.mkdir(parents=True, exist_ok=True)

    match group_str:
        case "nrcan":

            retrieve_miniseed(scode_alias,date,proc_dir=proc_dir,cha_list=cha_list,obspy_select_kwargs)
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