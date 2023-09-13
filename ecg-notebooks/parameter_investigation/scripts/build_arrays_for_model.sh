#!/bin/bash

for TARGET in hard_time gsmf_phi0 gsmf_mchar0_log10 mmb_mamp_log10 mmb_scatter_dex hard_gamma_inner
do 
    python ecg-notebooks/parameter_investigation/scripts/build_arrays_for_model.py $TARGET --favg -r 500 -v 21 --bgl 1

done


for TARGET in gsmf_phi0 gsmf_mchar0_log10 mmb_mamp_log10 mmb_scatter_dex
do 
    python ecg-notebooks/parameter_investigation/scripts/build_arrays_for_model.py $TARGET --favg -r 500 -v 21 --bgl 1 --gw_only

done