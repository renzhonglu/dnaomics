#!/usr/bin/env python
# AUTHOR: P. Christoph Champ <champc@uw.edu>
# DATE: 2012-09-25
# LAST UPDATE: 2012-10-08
# TODO: Add a complete description of this module
# DESCRIPTION: Reads in two files in TAB format ...
import numpy as np
from pandas import DataFrame, Series

## Local modules
import csv_io
import statistics
from utils import min_gt

def vet_data(data_frame):
    """Performs various checks on the input files returning any errors found.
    """
    ## TODO: Add a _lot_ more sanity/vetting checks!
    err = ''

    ## Print out a list of GOs whose abundances sum to 0.0
    #for i in range(full_abund_df.shape[0]):
    #    if full_abund_df.ix[i].sum() == 0.0:
    #        print full_abund_df.index.tolist()[i]

    ## Make sure there are only 2 classes in the metafile.
    num_uniq_classes = len(
        list(set([ c[0] for c in data_frame.values.tolist() ])))
    if num_uniq_classes != 2:
        err  = "ERROR: There are %s unique classes in the metafile. " % (
            num_uniq_classes)
        err += "Expecting 2 unique classes."
    return err

def calc_statistics(abund_file, meta_file, stats_file, control_id, 
                    which_statistics):
    """Runs the main analysis on the two input files.
    """
    ## Initialize go_list as empty, which will stay empty if there are any
    ## errors with the input files and/or the statistics
    go_list = ''

    ## Read data files into DataFrames.
    raw_abund_df = csv_io.csv_to_data_frame(abund_file)
    meta_df = csv_io.csv_to_data_frame(meta_file)

    ## Normalize data values (i.e., each row sums to 1.0)
    ## Note: For rows that sum to 0.0, force the values for each cell to be
    ## 0.0 instead of NaN
    #abund_df = DataFrame(np.nan_to_num(
    #                     [ tmp_abund_df.ix[i] / tmp_abund_df.ix[i].sum() 
    #                       for i in tmp_abund_df.index ]),
    #                     columns=tmp_abund_df.columns,
    #                     index=tmp_abund_df.index)
    #abund_df = abund_df.apply(lambda x: x + abund_df.min(1))
    min_vals = list(raw_abund_df.apply(
                   lambda x: min_gt(x, 0), axis=0).values.tolist())
    #abund_df = abund_df.add(min_vals, axis=1)
    raw_abund_df += min_vals
    sum_columns_list = raw_abund_df.sum(0).values.tolist()
    #abund_df = abund_df.apply(lambda x: x / abund_df.sum(1))
    abund_df = raw_abund_df / sum_columns_list

    ## Run various checks on the input files. Exit printing errors.
    err = vet_data(meta_df)
    if err != '':
        return go_list, err

    ## Create a list of "row names" from the various DataFrames to use as
    ## indices or column names
    index_ids = list([i for i in abund_df.index])
    sample_ids = list([i for i in meta_df.index])
    class_ids = list(set([ c[0] for c in meta_df.values.tolist() ]))

    ## Check to see if the user supplied control_id exists in the metafile
    control_id = str(control_id)
    if control_id not in class_ids:
        err  = "control_id = '%s' not found in metafile " % control_id
        err += "from available class_ids: %s" % (','.join(class_ids))
        return go_list, err

    ## Assign the disease_id to the opposite of the control_id (there should
    ## only be 2 unique class ids listed in the metafile!)
    disease_id = [ c for c in class_ids if not c == control_id ][0]

    ## Create a dicionary containing the class_ids as the keys and the 
    ## sample_ids as the values.
    ## E.g., {'Control': ['S1', 'S2'], 'Disease': ['S3', 'S4']}
    sample_dict = {}
    for c in class_ids:
        sample_dict[c] = [ s for s in sample_ids if meta_df.ix[s] == c ]

    ## Create separate DataFrame for the "control" and "disease" samples
    control_df = abund_df[[ s for s in sample_dict[control_id] ]]
    disease_df = abund_df[[ s for s in sample_dict[disease_id] ]]

    ## Calculate the odds ratio, log2(odds ratio), and update the DataFrame
    odds_ratio = statistics.calc_odds_ratio(control_df, disease_df)
    print "100% ODDS_RATIO"
    print odds_ratio
    print "-"*30
    log2_OR = np.log2(odds_ratio)
    ## FIXME: Figure out how to round values in a Series
    #odds_ratio = Series([ round(i, 6) for i in odds_ratio.tolist() ])
    #log2_OR = Series([ round(i, 6) for i in log2_OR.tolist() ])
    abund_df['odds_ratio'] = odds_ratio
    abund_df['log2_OR'] = log2_OR
    #print "OR>=1.0: ",sum(log2_OR.dropna() >= 1.0) ## DEBUG

    ## Perform whichever tests/statistics are defined in 'which_statistics'
    ## (e.g., t-Test, Wilcoxon, mean ratios, etc.) and update the DataFrame
    ## FIXME: This is a _REALLY_ bad way to do this!
    if 'ttest' in which_statistics:
        results = abund_df.apply(statistics.calc_ttest,
                                control=list(control_df.columns), 
                                disease=list(disease_df.columns), 
                                axis=1)
        abund_df['ttest'] = results['ttest']

    if 'wilcoxon' in which_statistics:
        results = abund_df.apply(statistics.calc_wilcoxon,
                                control=list(control_df.columns), 
                                disease=list(disease_df.columns), 
                                axis=1)
        abund_df['wilcoxon'] = results['wilcoxon']

    if 'ranksums' in which_statistics:
        results = abund_df.apply(statistics.calc_ranksums,
                                control=list(control_df.columns), 
                                disease=list(disease_df.columns), 
                                axis=1)
        abund_df['ranksums'] = results['ranksums']

    if 'mean_ratio' in which_statistics:
        results = abund_df.apply(statistics.calc_mean_ratio,
                                control=list(control_df.columns), 
                                disease=list(disease_df.columns), 
                                axis=1)
        abund_df['mean_ratio'] = results['mean_ratio']

    ## DataFrame containing all of the statistics run on the abund_filename
    stats_df = abund_df[which_statistics]

    ## Save statistics DataFrame to file
    csv_io.data_frame_to_csv(stats_df, stats_file)

    ## Save list of GOs to file (one GO per line)
    #f = open(out_go_list_filename, 'w')
    #f.write('\n'.join(index_ids))
    #f.close()

    ## Return go_list and, hopefully, an empty err string
    return list(index_ids), err
