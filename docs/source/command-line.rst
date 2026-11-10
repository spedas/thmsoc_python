Command-line tools
==================

Install the project before using these commands. Each section below is
generated directly from the corresponding :mod:`argparse` parser, so it stays
in sync with the command's ``--help`` output.

cdf_updater
-----------

.. argparse::
   :module: thmsoc.cli.cdf_updater
   :func: build_parser
   :prog: cdf_updater

product_volume
--------------

.. argparse::
   :module: thmsoc.cli.product_volume
   :func: build_parser
   :prog: product_volume

gen_l2_batches
--------------

.. argparse::
   :module: thmsoc.cli.gen_l2_batches
   :func: build_parser
   :prog: gen_l2_batches

gen_summary_plot_batches
------------------------

.. argparse::
   :module: thmsoc.cli.gen_summary_plot_batches
   :func: build_parser
   :prog: gen_summary_plot_batches

gen_scmode_batches
-------------------

.. argparse::
   :module: thmsoc.cli.gen_scmode_batches
   :func: build_parser
   :prog: gen_scmode_batches

gmag_retrieve_alternate
-----------------------
.. argparse::
   :module: thmsoc.cli.gmag_retrieve_alternate
   :func: build_parser
   :prog: gmag_retrieve_alternate

gmag_retrieve_usgs_variometer
-----------------------------

.. argparse::
   :module: thmsoc.cli.gmag_retrieve_usgs_variometer
   :func: build_parser
   :prog: gmag_retrieve_usgs_variometer

ip_owner_report
---------------

Group IPv4 request addresses by registered organization and current origin
ASN. Input may be read from a file or standard input; output is tab-separated.

.. argparse::
   :module: thmsoc.cli.ip_owner_report
   :func: build_parser
   :prog: ip_owner_report

ip_rdns_report
--------------

Aggregate IPv4 addresses and hostnames by their reverse-DNS domain. Input may
be read from a file or standard input; output is tab-separated.

.. argparse::
   :module: thmsoc.cli.ip_rdns_report
   :func: build_parser
   :prog: ip_rdns_report

web_traffic_report
------------------

Summarize an entire Apache access log by default. Every report prints
``Requests: N``, ``Matches: N``, and ``Non-matches: N``. Requests counts every
input line, including lines skipped because they could not be parsed.
The report also shows ``Total volume: N.N MB``, the sum of logged response
bytes for matching requests (1 MB = 1,000,000 bytes). A missing byte count
contributes zero.

Use ``--save_matches FILE`` to save original matching log lines in input order,
without counts or headings. Use ``--save_ips FILE``, ``--save_user_agents FILE``,
``--save_urls FILE``, ``--save_referer FILE``, and ``--save_responses FILE`` to
save all distinct matching values with counts, sorted by descending count
(ties by descending value).
Each option also prints its top 25 values and total unique count to the
console. Unrequested sections are omitted. Missing user agents and referers
are counted as ``-``.
Saved count files contain only count/value rows. Output files are overwritten
and must differ from the input and each other.

Use ``--latest N`` for the last N complete minutes, excluding the current
minute. For a fixed window, supply both ``--start_time`` and ``--end_time``.
The start is inclusive and the end is exclusive. Use ISO 8601 timestamps
with a UTC offset or ``Z`` for UTC; times without offsets use the machine's
local time. The log's own offsets are used when comparing timestamps.
Use ``--ip`` to match a literal substring anywhere in the source IP address,
or quote a shell glob to match the whole address. Repeat ``--ip`` to require
every IP pattern.

Use ``--response`` and ``--not_response`` to include or exclude whole
three-digit HTTP status codes. Both accept shell globs: ``200`` matches
exactly 200, ``4??`` matches any 4xx, and ``[45]??`` matches any 4xx or 5xx.
Quote patterns containing wildcards. All inclusion patterns must match,
and any matching exclusion rejects the request.

Use ``--url`` to search the logged request target (including its query
string). Use ``--user_agent`` and ``--referer`` to search the corresponding
fields in the Apache combined log. Use ``--not_url``, ``--not_user_agent``,
and ``--not_referer`` to exclude matches. These options accept
case-sensitive Python regular expressions; add ``(?i)`` for
case-insensitive matching. Quote patterns in the shell and escape regex
metacharacters for literal matches. Requests must pass every supplied filter,
including repeated options. Missing user agents and referers fail their
inclusion filters and pass their exclusions.

.. code-block:: bash

   web_traffic_report --latest 10 --response '[45]??' --ip '128.32.*.*' --save_ips ips.txt
   web_traffic_report --response '4??' --not_response 404 --save_responses responses.txt
   web_traffic_report --ip 128.32
   web_traffic_report --url 'api/v[0-9]+' --not_url 'health|metrics'
   web_traffic_report --user_agent 'Mozilla' --not_user_agent '(?i)bot' --save_matches requests.log
   web_traffic_report --save_ips ips.txt --save_urls urls.txt --save_user_agents agents.txt
   web_traffic_report --referer 'example\.org' --not_referer '/admin/' --save_referer referers.txt
   web_traffic_report --start_time 2026-11-10T12:00:00Z --end_time 2026-11-10T13:00:00Z

.. argparse::
   :module: thmsoc.cli.web_traffic_report
   :func: build_parser
   :prog: web_traffic_report

download_bz_recovery_data
-------------------------

Download Bz recovery ``.sav`` files for one or more probes and years from the
Nextcloud public share. FGL files are downloaded by default; ``--type`` may
select FGL or FGS. Remote filenames are preserved exactly, including a probe
prefix when present. Files are placed below
``PROBE/l1b/fgm/sav_files/YYYY`` under the download directory.

With ``--process-downloads``, the command runs the IDL
``process_bz_downloads`` routine after all downloads finish. Its batch file,
separate standard-output and standard-error logs, and final status file are
written under the working directory. The production, working, temporary, and
download roots can be overridden with command-line options; otherwise they are
derived from ``output_dataroot`` and ``temproot`` in the project configuration.

Passwordless public shares need no prompt. If a share is password protected,
the command prompts for its password after the first authentication attempt.

.. argparse::
   :module: thmsoc.cli.download_bz_recovery_data
   :func: build_parser
   :prog: download_bz_recovery_data
