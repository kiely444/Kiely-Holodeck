#!/bin/bash


# for TARGET in hard_time gsmf_mchar0_log10 mmb_mamp_log10 mmb_scatter_dex hard_gamma_inner
# do 
#     python ecg-notebooks/parameter_investigation/detect_model_clbrt_pta.py $TARGET --construct --debug -r 500 -v 3 -l 1000 
# done

# # gw only
# for TARGET in gsmf_phi0 gsmf_mchar0_log10 mmb_mamp_log10 mmb_scatter_dex 
# do 
#     python ecg-notebooks/parameter_investigation/detect_model_clbrt_pta.py $TARGET --construct --debug -r 500 -v 3 -l 1000 --gw_only
# done


# red noise for gw only
# gw only
for TARGET in gsmf_phi0 gsmf_mchar0_log10 mmb_mamp_log10 mmb_scatter_dex 
do 
    python ecg-notebooks/parameter_investigation/detect_model_clbrt_pta.py $TARGET --detstats --debug -r 500 -s 100 -v 21 -l 10 --bgl 1 --red2white 0.5 --red_gamma -1.5 --gw_only
    python ecg-notebooks/parameter_investigation/detect_model_clbrt_pta.py $TARGET --detstats --debug -r 500 -s 100 -v 21 -l 10 --bgl 1 --red2white 0.5 --red_gamma -3.0 --gw_only
    python ecg-notebooks/parameter_investigation/detect_model_clbrt_pta.py $TARGET --detstats --debug -r 500 -s 100 -v 21 -l 10 --bgl 1 --red2white 1.0 --red_gamma -1.5 --gw_only
    python ecg-notebooks/parameter_investigation/detect_model_clbrt_pta.py $TARGET --detstats --debug -r 500 -s 100 -v 21 -l 10 --bgl 1 --red2white 1.0 --red_gamma -3.0 --gw_only
    python ecg-notebooks/parameter_investigation/detect_model_clbrt_pta.py $TARGET --detstats --debug -r 500 -s 100 -v 21 -l 10 --bgl 1 --red2white 2.0 --red_gamma -1.5 --gw_only
    python ecg-notebooks/parameter_investigation/detect_model_clbrt_pta.py $TARGET --detstats --debug -r 500 -s 100 -v 21 -l 10 --bgl 1 --red2white 2.0 --red_gamma -3.0 --gw_only

done