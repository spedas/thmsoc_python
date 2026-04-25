from pyspedas import time_string, time_double
from thmsoc import args_to_startend
from thmsoc import batch_daterange
from thmsoc import datelist_to_string
from pathlib import Path

def make_l2_batches(start_date, end_date, days, days_per_batch, l2_types, probes, output_directory):
    start, end = args_to_startend(start_date,end_date,days)
    output_path = Path(output_directory)
    output_path.mkdir(parents=True, exist_ok=True)
    master_list_path = output_path / "master_list.txt"
    with open(master_list_path, 'w') as m:
        for batch in batch_daterange(start,end,days_per_batch):
            for probe in probes:
                batch_dates = datelist_to_string(batch)
                basename = f"batch_{batch_dates[0]}_probe_{probe}.bm"
                batchfile_path = output_path / basename
                with open(batchfile_path,'w') as f:
                    f.write(f"thm_reprocess_l2gen_days,{batch_dates},{l2_types},'{probe}'\n")
                    f.write(f"exit\n",)
                m.write(f"{basename}\n")

if __name__ == "__main__":
    make_l2_batches('2024-05-25','2026-01-01',None,7, l2_types=['fit', 'fgm'], probes=['e'], output_directory='/tmp/gen_l2_batches')
