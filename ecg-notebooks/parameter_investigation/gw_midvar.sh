#!/bin/bash



python ecg-notebooks/parameter_investigation/detect_model_varclbrt.py gsmf_phi0 --detstats --debug -r 500 -s 100 -v 21 --cv 10 --gw_only

python ecg-notebooks/parameter_investigation/detect_model_varclbrt.py gsmf_mchar0_log10 --detstats --debug -r 500 -s 100 -v 21 --cv 10 --gw_only

python ecg-notebooks/parameter_investigation/detect_model_varclbrt.py mmb_mamp_log10 --detstats --debug -r 500 -s 100 -v 21 --cv 10 --gw_only

python ecg-notebooks/parameter_investigation/detect_model_varclbrt.py mmb_scatter_dex --detstats --debug -r 500 -s 100 -v 21 --cv 10 --gw_only
