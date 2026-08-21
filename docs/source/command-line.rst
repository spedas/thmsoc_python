Command-line tools
==================

Install the project before using these commands. Each section below is
generated directly from the corresponding :mod:`argparse` parser, so it stays
in sync with the command's ``--help`` output.

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

download_bz_recovery_data
-------------------------

Download Bz recovery ``.sav`` files for one probe and year from the Nextcloud
public share. FGS files are downloaded by default; ``--type`` selects FGL,
FGS, or both. Remote filenames are preserved exactly, including a probe prefix
when present. Files are installed below
``PROBE/l1b/fgm/sav_files/YYYY`` under the configured ``output_dataroot``.

Passwordless public shares need no prompt. If a share is password protected,
the command prompts for its password after the first authentication attempt.

.. argparse::
   :module: thmsoc.cli.download_bz_recovery_data
   :func: build_parser
   :prog: download_bz_recovery_data
