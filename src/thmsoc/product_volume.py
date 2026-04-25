from __future__ import annotations
import pandas as pd
from dataclasses import dataclass, asdict, replace
from typing import Optional
from pathlib import Path
from glob import glob
import tomli
from datetime import datetime, date
from thmsoc.daterange import simple_daterange, args_to_startend


def get_categories() -> dict:
    thmsoc_python_root = Path(__file__).resolve().parent.parent.parent
    thmsoc_python_config = thmsoc_python_root / "thmsoc_python_config.toml"

    try:
        with open(thmsoc_python_config, "rb") as f:
            toml_dict = tomli.load(f)
            DATAROOT = toml_dict["paths"]["input_dataroot"]

    except FileNotFoundError:
        DATAROOT = "/disks/themisdata"


    PROBES = ["tha", "thb", "thc", "thd", "the"]

    L1_TYPES = [
        "bau", "eff", "efp", "efw", "esa", "fbk",
        "fff_16", "fff_32", "fff_64",
        "ffp_16", "ffp_32", "ffp_64",
        "ffw_16", "ffw_32", "ffw_64",
        "fgm", "fit", "hsk", "mom",
        "scmode", "scf", "scp", "scw", "sst", "state",
        "trg", "vaf", "vap", "vaw", "vbf", "vbp", "vbw",
    ]

    L1_TYPES_TO_INST = {
        "bau": "BAU",
        "eff": "EFI",
        "efp": "EFI",
        "efw": "EFI",
        "vaf": "EFI",
        "vap": "EFI",
        "vaw": "EFI",
        "vbf": "EFI",
        "vbp": "EFI",
        "vbw": "EFI",
        "fbk": "EFI+SCM",
        "fgm": "FGM",
        "fit": "FGM+EFI",
        "fff_16": "EFI+SCM",
        "fff_32": "EFI+SCM",
        "fff_64": "EFI+SCM",
        "ffp_16": "EFI+SCM",
        "ffp_32": "EFI+SCM",
        "ffp_64": "EFI+SCM",
        "ffw_16": "EFI+SCM",
        "ffw_32": "EFI+SCM",
        "ffw_64": "EFI+SCM",
        "hsk": "IDPU",
        "trg": "IDPU",
        "state": "IDPU",
        "esa": "ESA",
        "sst": "SST",
        "mom": "ESA+SST",
        "scf": "SCM",
        "scp": "SCM",
        "scw": "SCM",
        "scmode": "IDPU",
    }

    L2_TYPES = [
        "efi", "esa", "esd", "fbk", "fft", "fgm",
        "fit", "gmom", "mom", "scm", "sst", "efw", "efp",
    ]

    L2_TYPES_TO_INST = {
        "efi": "EFI",
        "esa": "ESA",
        "esd": "ESA",
        "fbk": "EFI+SCM",
        "fft": "EFI+SCM",
        "fgm": "FGM",
        "fit": "EFI+FGM",
        "gmom": "ESA+SST",
        "mom": "ESA+SST",
        "scm": "SCM",
        "sst": "SST",
        "efw": "EFI",
        "efp": "EFI"
    }

    ASI_SITES = [
        "atha", "chbg", "ekat", "fsim", "fsmi", "fykn", "galo", "gbay",
        "gill", "inuv", "kapu", "kian", "kuuj", "mcgr", "nrsq", "pgeo",
        "pina", "rank", "snap", "snkq", "talo", "tpas", "whit", "yknf",
    ]

    REGO_SITES = [
        "atha","fsim","fsmi","gill","kakt","luck","lyrn","rank","resu","sach", "talo",
    ]
    return(
        {
            "DATAROOT":DATAROOT,
            "PROBES":PROBES,
            "L1_TYPES":L1_TYPES,
            "L1_TYPES_TO_INST":L1_TYPES_TO_INST,
            "L2_TYPES":L2_TYPES,
            "L2_TYPES_TO_INST":L2_TYPES_TO_INST,
            "ASI_SITES":ASI_SITES,
            "REGO_SITES":REGO_SITES,
        }
    )
@dataclass
class Measurement:
    date: date
    domain: str                      # "probe", "ground", "plots", etc.
    category: str                    # "vc", "l0", "l1", "l2", "asi_cdf", ...
    bytes: int

    probe: Optional[str] = None      # tha, thb, ...
    level: Optional[str] = None      # vc, l0, l1, l2
    instrument: Optional[str] = None # fgm, esa, asi, ...
    product_type: Optional[str] = None # 405, fff_16, gmom
    site: Optional[str] = None       # atha, chbg, ...
    estimated: bool = False
    file_count: int = 0
    path_pattern: Optional[str] = None
    notes: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

def measurements_to_dataframe(measurements: list[Measurement]) -> pd.DataFrame:
    df = pd.DataFrame([m.to_dict() for m in measurements])

    if not df.empty:
        df["gb"] = df["bytes"] / 1_000_000_000.0

    return df

def summarize_day(df: pd.DataFrame) -> None:
    print("\nBy category:")
    print(df.groupby("category", dropna=False)["bytes"].sum().sort_values(ascending=False))

    print("\nBy probe:")
    probe_df = df[df["probe"].notna()]
    print(probe_df.groupby("probe")["bytes"].sum().sort_values(ascending=False))

    print("\nBy probe and level:")
    print(
        probe_df.groupby(["probe", "level"], dropna=False)["bytes"]
        .sum()
        .sort_values(ascending=False)
    )

    print("\nGround categories:")
    ground_df = df[df["domain"] == "ground"]
    print(ground_df.groupby("category")["bytes"].sum().sort_values(ascending=False))

def shell_style_totals(df: pd.DataFrame) -> dict[str, float]:
    probe_total = df[df["domain"] == "probe"]["bytes"].sum()

    probe_vc_total = df[(df["domain"] == "probe") & (df["level"]=="vc")]["bytes"].sum()
    probe_l0_total = df[(df["domain"] == "probe") & (df["level"]=="l0")]["bytes"].sum()
    probe_l1_total = df[(df["domain"] == "probe") & (df["level"]=="l1")]["bytes"].sum()
    probe_l2_total = df[(df["domain"] == "probe") & (df["level"]=="l2")]["bytes"].sum()

    orbits_total = df[df["category"].isin(["orbits"])]["bytes"].sum()
    summary_total = df[df["category"].isin(["summary"])]["bytes"].sum()
    asi_images_total = df[df["category"].isin(["asi_images"])]["bytes"].sum()
    plots_total = df[df["category"].isin(["orbits", "summary", "asi_images"])]["bytes"].sum()

    asi_total = df[df["category"].isin(["keograms", "asi_cdf"])]["bytes"].sum()
    keograms_total = df[df["category"].isin(["keograms"])]["bytes"].sum()
    asi_cdf_total = df[df["category"].isin(["asi_cdf"])]["bytes"].sum()

    rego_keograms_total = df[df["category"].isin(["rego_keograms"])]["bytes"].sum()
    rego_cdf_total = df[df["category"].isin(["rego_cdf"])]["bytes"].sum()


    gmag_total = df[df["category"].isin(["idx", "l2mag"])]["bytes"].sum()
    idx_total = df[df["category"].isin(["idx"])]["bytes"].sum()
    gmagl2_total = df[df["category"].isin(["l2mag"])]["bytes"].sum()

    return {
        "Probes (vc, l0, l1, l2)": probe_total,
        "Probe VC": probe_vc_total,
        "Probe L0": probe_l0_total,
        "Probe L1": probe_l1_total,
        "Probe L2": probe_l2_total,
        "Orbit Plots": orbits_total,
        "Summary Plots": summary_total,
        "ASI images": asi_images_total,
        "keograms": keograms_total,
        "REGO keograms": rego_keograms_total,
        "REGO CDFs": rego_cdf_total,
        "asi_cdf": asi_cdf_total,
        "Plots": plots_total,
        "ASI": asi_total,
        "GMAG": gmag_total,
        "idx": idx_total,
        "gmagl2": gmagl2_total,
        "ground_total": asi_images_total + keograms_total + rego_keograms_total + rego_cdf_total + asi_cdf_total + gmag_total,

    }

def date_parts(day: date) -> dict[str, str]:
    return {
        "YYYY": day.strftime("%Y"),
        "MM": day.strftime("%m"),
        "DD": day.strftime("%d"),
        "DOY": day.strftime("%j"),
        "YYYYMMDD": day.strftime("%Y%m%d"),
        "YYYY_MM_DD": day.strftime("%Y-%m-%d"),
    }

def make_l0_measurement(
    *,
    day: date,
    domain: str,
    category: str,
    path: Path,
    probe: str | None = None,
    level: str | None = None,
    instrument: str | None = None,
    product_type: str | None = None,
    site: str | None = None,
    estimated: bool = False,
    notes: str | None = None,
) -> Measurement:
    total_bytes = 0
    file_count = 0

    try:
        if path.is_file():
            total_bytes = path.stat().st_size
            file_count = 1
    except OSError:
        # Skip unreadable / transient files
        total_bytes = 0
        file_count = 0

    return Measurement(
        date=day,
        domain=domain,
        category=category,
        bytes=total_bytes,
        probe=probe,
        level=level,
        instrument=instrument,
        product_type=product_type,
        site=site,
        estimated=estimated,
        file_count=file_count,
        path_pattern=path.name,
        notes=notes,
    )


def make_measurement(
    *,
    day: date,
    domain: str,
    category: str,
    pattern: str,
    probe: str | None = None,
    level: str | None = None,
    instrument: str | None = None,
    product_type: str | None = None,
    site: str | None = None,
    estimated: bool = False,
    notes: str | None = None,
) -> Measurement:
    total_bytes, file_count = sum_file_sizes(pattern)

    return Measurement(
        date=day,
        domain=domain,
        category=category,
        bytes=total_bytes,
        probe=probe,
        level=level,
        instrument=instrument,
        product_type=product_type,
        site=site,
        estimated=estimated,
        file_count=file_count,
        path_pattern=pattern,
        notes=notes,
    )

def sum_file_sizes(pattern: str) -> tuple[int, int]:
    """
    Return (total_bytes, file_count) for files matching a glob pattern.
    Missing matches are not an error; they return (0, 0).
    """
    total = 0
    count = 0

    for name in glob(pattern):
        path = Path(name)
        try:
            if path.is_file():
                total += path.stat().st_size
                count += 1
        except OSError:
            # Skip unreadable / transient files
            continue

    return total, count

def apid2inst(apid:str) -> str:
    apid=apid.lower()
    if apid in {"405", "460", "461"}:
        return "FGM"
    if apid in {"410"}:
        return "FGM+EFI"
    if apid in {"440","44d","44e","44f"}:
        return "EFI+SCM"
    if apid in {"441", "442", "443", "445", "446", "447", "449", "44a", "44b"}:
        return "EFI"
    if apid in {"444", "448", "44c"}:
        return "SCM"
    if apid in {"453"}:
        return "ESA+SST"
    if apid in {"454", "455", "456", "457", "458", "459"}:
        return "ESA"
    if apid in {"452", "45a", "45b", "45c", "45d", "45e", "45f"}:
        return "SST"
    if apid in {"404", "406", "451"}:
        return "IDPU"
    if apid.startswith("3"):
        return "BAU"
    return "unknown"

def split_measurement(row: Measurement) -> list[Measurement]:
    total_bytes = row.bytes
    inst_string = row.instrument
    inst_split = inst_string.split("+")
    r1 = replace(row,instrument=inst_split[0],bytes=int(total_bytes/2.0))
    r2 = replace(row,instrument=inst_split[1],bytes=int(total_bytes/2.0))
    return([r1,r2])


def scan_day(day: date, categories_dict: dict) -> list[Measurement]:
    parts = date_parts(day)
    YYYY = parts["YYYY"]
    MM = parts["MM"]
    DD = parts["DD"]
    DOY = parts["DOY"]
    YYYYMMDD = parts["YYYYMMDD"]

    rows: list[Measurement] = []

    DATAROOT=categories_dict["DATAROOT"]
    PROBES=categories_dict["PROBES"]
    L1_TYPES=categories_dict["L1_TYPES"]
    L1_TYPES_TO_INST=categories_dict["L1_TYPES_TO_INST"]
    L2_TYPES=categories_dict["L2_TYPES"]
    L2_TYPES_TO_INST=categories_dict["L2_TYPES_TO_INST"]
    ASI_SITES=categories_dict["ASI_SITES"]
    REGO_SITES=categories_dict["REGO_SITES"]

    # Probe data
    for probe in PROBES:
        # VC
        patt = f"{DATAROOT}/{probe}/vc_archive/{YYYY}/*{YYYY}_{DOY}*"
        rows.append(
            make_measurement(
                day=day,
                domain="probe",
                category="vc",
                level="vc",
                probe=probe,
                pattern=patt,
            )
        )

        # L0
        patt = f"{DATAROOT}/{probe}/l0/{YYYY}/{MM}/{DD}/*"

        for name in glob(patt):
            path = Path(name)
            basename = path.name
            apid = basename[7:10]
            inst = apid2inst(apid)
            row =  make_l0_measurement(
                    day=day,
                    domain="probe",
                    category="l0",
                    level="l0",
                    instrument=inst,
                    product_type=apid.lower(),
                    probe=probe,
                    path=path,
                )
            if "+" in inst:
                rows.extend(split_measurement(row))
            else:
                rows.append(row)


        # L1 by type
        for l1type in L1_TYPES:
            patt = f"{DATAROOT}/{probe}/l1/{l1type}/{YYYY}/*{YYYYMMDD}*"
            inst = L1_TYPES_TO_INST[l1type]
            row = make_measurement(
                    day=day,
                    domain="probe",
                    category="l1",
                    level="l1",
                    probe=probe,
                    product_type=l1type,
                    instrument=inst,
                    pattern=patt,
                )
            if "+" in inst:
                rows.extend(split_measurement(row))
            else:
                rows.append(row)

        # L2 by type
        for l2type in L2_TYPES:
            patt = f"{DATAROOT}/{probe}/l2/{l2type}/{YYYY}/*{YYYYMMDD}*"
            inst = L2_TYPES_TO_INST[l2type]

            row = make_measurement(
                    day=day,
                    domain="probe",
                    category="l2",
                    level="l2",
                    probe=probe,
                    product_type=l2type,
                    instrument=inst,
                    pattern=patt,
                )
            if "+" in inst:
                rows.extend(split_measurement(row))
            else:
                rows.append(row)

    # Ground / plots
    patt = f"{DATAROOT}/thg/l0/asi/{YYYY}/{MM}/*{YYYY}-{MM}-{DD}*"
    rows.append(
        make_measurement(
            day=day,
            domain="ground",
            category="orbits",
            instrument="asi",
            level="l0",
            pattern=patt,
        )
    )

    patt = f"{DATAROOT}/overplots/{YYYY}/{MM}/{DD}/*"
    rows.append(
        make_measurement(
            day=day,
            domain="ground",
            category="summary",
            pattern=patt,
        )
    )

    patt = f"{DATAROOT}/thg/l1/asi/ask/{YYYY}/*{YYYYMMDD}*"
    rows.append(
        make_measurement(
            day=day,
            domain="ground",
            category="keograms",
            instrument="asi",
            level="l1",
            pattern=patt,
        )
    )

    daily_asi_total = 0

    for site in ASI_SITES:
        patt = f"{DATAROOT}/thg/l1/asi/{site}/{YYYY}/{MM}/*{YYYYMMDD}*"
        m = make_measurement(
            day=day,
            domain="ground",
            category="asi_cdf",
            instrument="asi",
            level="l1",
            site=site,
            pattern=patt,
        )
        rows.append(m)
        daily_asi_total += m.bytes

    # Estimated ASI images
    rows.append(
        Measurement(
            date=day,
            domain="ground",
            category="asi_images",
            bytes=int(daily_asi_total * 0.1),
            instrument="asi",
            estimated=True,
            file_count=0,
            path_pattern=None,
            notes="Estimated as 10% of ASI CDF total",
        )
    )

    # Calgary REGO CDFs
    for site in REGO_SITES:
        patt = f"{DATAROOT}/thg/l1/reg/{site}/{YYYY}/{MM}/*{YYYYMMDD}*"
        m = make_measurement(
            day=day,
            domain="ground",
            category="rego_cdf",
            instrument="asi",
            level="l1",
            site=site,
            pattern=patt,
        )
        rows.append(m)

    # REGO keograms

    patt = f"{DATAROOT}/thg/l1/reg/ask/{YYYY}/*{YYYYMMDD}*"
    rows.append(
        make_measurement(
            day=day,
            domain="ground",
            category="rego_keograms",
            instrument="asi",
            level="l1",
            pattern=patt,
        )
    )

    # AE index
    patt = f"{DATAROOT}/thg/l1/mag/idx/{YYYY}/*{YYYYMMDD}*"
    rows.append(
        make_measurement(
            day=day,
            domain="ground",
            category="idx",
            instrument="mag",
            level="l1",
            pattern=patt,
        )
    )

    # Raw magnetometer data, 3-char and 4-char site codes
    patt = f"{DATAROOT}/thg/l2/mag/???/{YYYY}/*{YYYYMMDD}*"
    rows.append(
        make_measurement(
            day=day,
            domain="ground",
            category="l2mag",
            instrument="mag",
            level="l2",
            pattern=patt,
            notes="3-character GMAG site codes",
        )
    )

    patt = f"{DATAROOT}/thg/l2/mag/????/{YYYY}/*{YYYYMMDD}*"
    rows.append(
        make_measurement(
            day=day,
            domain="ground",
            category="l2mag",
            instrument="mag",
            level="l2",
            pattern=patt,
            notes="4-character GMAG site codes",
        )
    )

    return rows

def run_product_volume(start_date:str=None, end_date:str = None, days:int = None) -> None:
    import sys
    # Set line buffering to avoid long pauses when viewing output with 'tail'
    sys.stdout.reconfigure(line_buffering=True)

    start, end = args_to_startend(start_date, end_date, days)

    all_measurements = []

    print(f"Processing date range: {start} to {end}\n")
    categories_dict = get_categories()

    for day in simple_daterange(start, end):
        print("=" * 60)
        print(f"Processing {day}")
        print("=" * 60)

        measurements = scan_day(day, categories_dict)
        df = measurements_to_dataframe(measurements)

        # Optional: print a compact per-day summary
        totals = shell_style_totals(df)

        print("Daily totals (GB):")
        for key, value in totals.items():
            print(f"  {key}: {value} (bytes) {value/1_000_000_000:.3f} (gb)")

        # Optional: more detailed breakdown
        summarize_day(df)

        all_measurements.extend(measurements)

    # ---- Final aggregate over entire range ----
    print("\n" + "#" * 60)
    print("FINAL TOTALS FOR DATE RANGE")
    print("#" * 60)

    df_all = measurements_to_dataframe(all_measurements)

    totals = shell_style_totals(df_all)

    print("Grand totals (GB):")
    for key, value in totals.items():
        print(f"{key}: {value/1_000_000_000:.3f}")

    # Optional: deeper breakdown
    print("\nBreakdown by category:")
    print(df_all.groupby("category")["gb"].sum().sort_values(ascending=False))

    # Optional: deeper breakdown
    print("\nProbe L0 Breakdown by instrument:")
    print(df_all[(df_all["domain"] == "probe") &  (df_all["level"]=="l0")].groupby("instrument")["gb"].sum().sort_values(ascending=False))

    print("\nProbe L1 Breakdown by instrument:")
    print(df_all[(df_all["domain"] == "probe") &  (df_all["level"]=="l1")].groupby("instrument")["gb"].sum().sort_values(ascending=False))

    print("\nProbe L2 Breakdown by instrument:")
    print(df_all[(df_all["domain"] == "probe") &  (df_all["level"]=="l2")].groupby("instrument")["gb"].sum().sort_values(ascending=False))

    print("\nProbe L0+L1+l2 Breakdown by instrument:")
    print(df_all[(df_all["domain"] == "probe") &  (df_all["level"]!="vc")].groupby("instrument")["gb"].sum().sort_values(ascending=False))

    print("Alternate L0+L1+L2 breakdown format")
    print(df_all[(df_all["domain"] == "probe") & (df_all["level"]!="vc")].groupby(["instrument", "level"])["gb"].sum())

if __name__ == '__main__':
    run_product_volume(start_date='2026-04-14',days=1)