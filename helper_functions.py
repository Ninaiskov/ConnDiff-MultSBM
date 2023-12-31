import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from sklearn.metrics.cluster import normalized_mutual_info_score
from PIL import Image
import nilearn as ni
from nilearn import plotting as nplt
import seaborn as sns
import matplotlib.image as mpimg
from sklearn import metrics
import networkx as nx
from scipy.stats import entropy
from scipy.sparse import load_npz, triu
from scipy.io import loadmat
from scipy.sparse import csr_matrix, load_npz, triu
from matplotlib.patches import Ellipse, Arc
from matplotlib.colors import Normalize
from matplotlib import colormaps

# main directory
main_dir = '/work3/s174162/speciale'
# general plotting parameters
label_fontsize = 15
legend_fontsize = 10
subtitle_fontsize = 16
title_fontsize = 18
dpi = 400
cmap_color=plt.cm.Greys

os.environ["OMP_NUM_THREADS"] = "10"  # set number of threads

def get_exp_overview(top_dir):
    ## INPUT
    # top_dir:  top-level results directory containing the log files, e.g. 'results/hcp/'
    
    ## OUTPUT
    # df_new:   Pandas DataFrame with experiment overview (containing the data from the log file)

    # Create an empty list to store the data from each log file
    data = []

    # Recursively iterate over all log files in the directory structure
    for root, dirs, files in os.walk(top_dir):
        for file_name in files:
            if file_name == 'log.txt':
                # Read the contents of the file
                with open(os.path.join(root, file_name), 'r') as f:
                    file_data = f.readlines()
                
                # Parse the data from the file and add it to the list
                file_dict = {}
                for line in file_data:
                    key, value = line.strip().split(': ')
                    # Try to convert the value to a number
                    try:
                        value = float(value)
                        # Check if the value is an integer and convert it if it is
                        if value.is_integer():
                            value = int(value)
                    except ValueError:
                        pass
                    file_dict[key] = value
                data.append(file_dict)

    # Convert the list of dictionaries to a Pandas DataFrame
    df = pd.DataFrame(data)
    df = df.fillna('None')
    
    # count experiment initializations
    config_names = df.columns.tolist()
    config_names.remove('exp_name')
    duplicated_rows = df.duplicated(subset=config_names)
    unique_rows = df[~duplicated_rows].copy()
    duplicate_count = df.groupby(config_names, as_index=False)['exp_name'].agg(list)
    duplicate_count['n_exp'] = duplicate_count['exp_name'].apply(len)
    df_new = unique_rows.merge(duplicate_count, on=config_names, how='left')
    df_new = df_new.drop('exp_name_x', axis=1)
    df_new = df_new.rename(columns={'exp_name_y': 'exp_name_list'})
    
    # save dataframe with experiment overview
    dataset = top_dir.split('/')[1]
    df_new.to_csv(os.path.join(top_dir,dataset+'_experiment_overview.csv'),index=False)
            
    return df_new


def generate_syndata(K, S1, S2, Nc_type, alpha, seed=0, save_data=False, disp_data = False, dataset='synthetic',
                     label_fontsize=label_fontsize, subtitle_fontsize=subtitle_fontsize, title_fontsize=title_fontsize, cmap_color=cmap_color):
    ## Inputs
    # K                     Number of clusters;
    # S1                    Number of first type of graph, e.g. healthy
    # S2                    Number of second type of graph, e.g. sick
    # Nc_type               Node distribution in clusters, either 'balanced' or 'unbalanced' no. of nodes in each cluster
    # alpha                 Scaling parameter controling similarity between population etas (alpha=0 --> completely different, alpha=0.5 --> same)
    
    # seed                  Random seed used
    # disp_data             Bool for displaying generated data
    # label_fontsize        Label fontsize
    # subtitle_fontsize     Subtitle fontsize
    # title_fontsize        Title fontsize
    
        # predefined: N = total number of nodes

    # Output
    # A = adjacency matrices for all subjects
    
    np.random.seed(seed)
    ### STEPS:
    ## 1) compute partition (Z) - original and expected
    N = 100 # the distribution of nodes sum up to 100
    # balanced or unbalanced
    if Nc_type == 'balanced':
        Nc = int(N/K)
        Z = np.kron(np.eye(K),np.ones((Nc,1)))
        Nc_list = np.repeat(Nc,K).tolist()
    elif Nc_type == 'unbalanced': 
        if K == 2:
            Nc_list = [70, 30]
        elif K == 5:
            Nc_list = [60, 20, 10, 5, 5]
        elif K == 10:
            Nc_list = [20, 20, 10, 10, 10, 10, 5, 5, 5, 5]
        else:
            print('Nc_list not specfied for chosen K')

        Z = np.zeros((N, K))
        for k in range(K): # len(Nc_list) = K
            Nc = Nc_list[k]
            cumsumNc = int(np.sum(Nc_list[:k]))
            Z[cumsumNc:cumsumNc+Nc, k] = 1
    else:
        print('Unknown Nc_type')
        
    ## 2) Computing population cluster-link probability matrices (eta_p1 and eta_p2)
    # defining eta-matrices: eta1 will always have high within compared to between cluster-linkprob. and vice versa with eta2.
    eta1 = np.random.choice(np.linspace(0,0.4,K*K),(K,K))
    eta1[np.diag_indices_from(eta1)] = np.ones(K)*0.9
    eta2 = 1-eta1 
        
    # making eta-matrices symmetric - only including the diagonal once!
    eta1 = np.triu(eta1, 1) + np.triu(eta1, 0).T  
    eta2 = np.triu(eta2, 1) + np.triu(eta2, 0).T

    # reparametrize alpha := 2*alpha
    eta_p1 = (1-alpha/2)*eta1 + alpha/2*eta2
    eta_p2 = alpha/2*eta1 + (1-alpha/2)*eta2
    # note similarity between eta_p1 and eta_p2 is controlled by the scaling parameter alpha which mixes eta1 and eta2 
   
    # if alpha = 0 --> eta_p1 = eta1 and eta_p2 = eta2 (completely different population etas)
    # if alpha = 0.5 --> eta_p1 = 1/2*(eta1+eta2) and eta_p2 = 1/2*(eta1+eta2) (same population etas)
    # if alpha \in ]0, 0.5[ --> eta_p1 and eta_p2 are partially different 
    
    # 3) Compute adjacency matrices (A)
    A = np.empty((N, N, S1+S2))
    A.fill(np.nan)
    M1 = Z @ eta_p1 @ Z.T
    M2 = Z @ eta_p2 @ Z.T
    randthres = np.random.rand(N, N, S1+S2)
    #randthres = np.random.rand(N,N)
    for s in range(S1+S2): # note two cases: S1=5, S2=5 and S1=10, S2=5
        if s <= S1-1:
            At = M1 > randthres[:,:,s]
            A[:,:,s] = np.triu(At, 1) + np. triu(At, 1).T
        else:
            At = M2 > randthres[:,:,s]
            A[:,:,s] = np.triu(At, 1) + np. triu(At, 1).T

    # 4) Computed expected partitions based on alpha and Nc_type
    diff_clusters = np.where(np.any(np.triu(eta_p1-eta_p2,0),axis=1))[0] # difference clusters
    if len(diff_clusters) > 0:
        remaining_nodes = np.delete(Nc_list, diff_clusters).sum() # nodes that are not a part of difference-clusters
        if remaining_nodes == 0:
            Nc_list_new = Nc_list
        else:
            Nc_list_new = np.append(Nc_list[diff_clusters],remaining_nodes)
        new_K = len(Nc_list_new)
        Zexp = np.zeros((N, new_K))
        for k in range(new_K):
            Nc = Nc_list[k]
            cumsumNc = int(np.sum(Nc_list_new[:k]))
            Zexp[cumsumNc:cumsumNc+Nc, k] = 1
    else: # no diff clusters 
        Zexp = np.ones((N,1))
 
    A_filename = 'A_'+str(K)+'_'+str(S1)+'_'+str(S2)+'_'+str(Nc_type)+'_{:.3g}'.format(alpha)
    Zini_filename = 'Zini_'+str(K)+'_'+str(Nc_type) # Zini_{K}_{Nc_type} "Initial / original partition matrix"
    Zexp_filename = 'Zexp_'+str(K)+'_'+str(Nc_type)+'_{:.2g}'.format(alpha)
    eta_filename = str(K)+'_{:.2g}'.format(alpha)

    # 5) Save data
    if save_data:
        np.save(os.path.join(main_dir,'data',dataset,A_filename+'.npy'), A)
        np.save(os.path.join(main_dir,'data',dataset,Zini_filename+'.npy'), Z)
        np.save(os.path.join(main_dir,'data',dataset,Zexp_filename+'.npy'), Zexp)
        np.save(os.path.join(main_dir,'data',dataset,'eta_p1_'+eta_filename+'.npy'), eta_p1)
        np.save(os.path.join(main_dir,'data',dataset,'eta_p2_'+eta_filename+'.npy'), eta_p2)

    # 6) Display data
    if disp_data:

        fig, ax = plt.subplots()
        cmap = ListedColormap(['w', 'k']) 
        im = ax.imshow(Z, interpolation='nearest', aspect='auto', cmap=cmap, extent=(0, Z.shape[1], 0, Z.shape[0]))
        ax.set_ylabel('Node', fontsize=label_fontsize)
        ax.set_xlabel('Cluster', fontsize=label_fontsize)
        ax.set_title('Initial partition $z_{ini}$', fontsize=title_fontsize, weight='bold')
        cbar = fig.colorbar(im, ax=ax, shrink=0.7, ticks=[0,1])
        plt.savefig(os.path.join(main_dir,'figures/article',Zini_filename+'.png'), bbox_inches='tight', dpi=dpi)

        fig, ax = plt.subplots()
        if Zexp.shape[1] == 1: #(only one cluster)
            cmap = ListedColormap(['k'])
        else:   
            cmap = ListedColormap(['w', 'k']) 
        im = ax.imshow(Zexp, interpolation='nearest', aspect='auto', cmap=cmap, extent=(0, Zexp.shape[1], 0, Zexp.shape[0]))
        ax.set_ylabel('Node', fontsize=label_fontsize)
        ax.set_xlabel('Cluster', fontsize=label_fontsize)
        ax.set_title('Expected partition $z_{exp}$', fontsize=title_fontsize, weight='bold')
        cbar = fig.colorbar(im, ax=ax, shrink=0.7, ticks=[0,1])
        plt.savefig(os.path.join(main_dir,'figures/article',Zexp_filename+'.png'), bbox_inches='tight', dpi=dpi)

        xy_ticks = range(0, K + 1, 1)
        cmap = cmap_color
        fig, ax = plt.subplots(1,2)
        plt.subplots_adjust(wspace=0.45, top=1.22)
        im = ax[0].imshow(eta_p1, cmap=cmap, extent=[0,K,K,0], vmin=0, vmax=1)
        ax[0].set_ylabel('Cluster', fontsize=label_fontsize)
        ax[0].set_xlabel('Cluster', fontsize=label_fontsize)
        ax[0].set_yticks(xy_ticks)
        ax[0].set_yticklabels(xy_ticks)
        ax[0].set_xticks(xy_ticks)
        ax[0].set_xticklabels(xy_ticks)
        ax[0].set_title('$\eta_{p1}$', fontsize=subtitle_fontsize, weight='bold')
        
        im = ax[1].imshow(eta_p2, cmap=cmap, extent=[0,K,K,0], vmin=0, vmax=1)
        ax[1].set_ylabel('Cluster', fontsize=label_fontsize)
        ax[1].set_xlabel('Cluster', fontsize=label_fontsize)
        ax[1].set_yticks(xy_ticks)
        ax[1].set_yticklabels(xy_ticks)
        ax[1].set_xticks(xy_ticks)
        ax[1].set_xticklabels(xy_ticks)
        ax[1].set_title('$\eta_{p2}$', fontsize=subtitle_fontsize, weight='bold')
        cbar = fig.colorbar(im, ax=ax.ravel().tolist(), shrink=0.3)
        fig.suptitle('Cluster-link probability matrices',fontsize=title_fontsize, weight='bold')
        plt.savefig(os.path.join(main_dir,'figures/article','eta_'+eta_filename+'_types.png'), bbox_inches='tight', dpi=dpi)

        
        fig, ax = plt.subplots(1,2)
        xy_ticks = range(0, N + 1, 20)
        cmap = cmap_color
        plt.subplots_adjust(wspace=0.45, top=1.1)
        im = ax[0].imshow(M1, cmap = cmap, vmin=0, vmax=1)
        ax[0].set_ylabel('Node', fontsize=label_fontsize)
        ax[0].set_xlabel('Node', fontsize=label_fontsize)
        ax[0].set_yticks(xy_ticks)
        ax[0].set_yticklabels(xy_ticks)
        ax[0].set_xticks(xy_ticks)
        ax[0].set_xticklabels(xy_ticks)
        ax[0].set_title('$M_{p1}$', fontsize=subtitle_fontsize, weight='bold')
        im = ax[1].imshow(M2, cmap = cmap, vmin=0, vmax=1)
        ax[1].set_ylabel('Node', fontsize=label_fontsize)
        ax[1].set_xlabel('Node', fontsize=label_fontsize)
        ax[1].set_yticks(xy_ticks)
        ax[1].set_yticklabels(xy_ticks)
        ax[1].set_xticks(xy_ticks)
        ax[1].set_xticklabels(xy_ticks)
        ax[1].set_title('$M_{p2}$', fontsize=subtitle_fontsize, weight='bold')
        cbar = fig.colorbar(im, ax=ax.ravel().tolist(), shrink=0.3)
        #fig.suptitle('$M$',fontsize=15, weight='bold')
        plt.savefig(os.path.join(main_dir,'figures/article', 'M_'+eta_filename+'_types.png'), bbox_inches='tight', dpi=dpi)
        
        xy_ticks = range(0, N + 1, 20)
        map_values = [0,1]
        colormap = plt.cm.Blues
        cmap = plt.cm.colors.ListedColormap(colormap(np.linspace(0, 1, len(map_values))))
        fig, ax = plt.subplots(1,2)
        plt.subplots_adjust(wspace=0.45, top=1.1)
        im = ax[0].imshow(A[:,:,0],cmap=cmap)
        ax[0].set_ylabel('Node', fontsize=label_fontsize)
        ax[0].set_xlabel('Node', fontsize=label_fontsize)
        ax[0].set_yticks(xy_ticks)
        ax[0].set_yticklabels(xy_ticks)
        ax[0].set_xticks(xy_ticks)
        ax[0].set_xticklabels(xy_ticks)
        ax[0].set_title('$A_{p1}$', fontsize=subtitle_fontsize, weight='bold')
        im = ax[1].imshow(A[:,:,-1], cmap=cmap)
        ax[1].set_ylabel('Node', fontsize=label_fontsize)
        ax[1].set_xlabel('Node', fontsize=label_fontsize)
        ax[1].set_yticks(xy_ticks)
        ax[1].set_yticklabels(xy_ticks)
        ax[1].set_xticks(xy_ticks)
        ax[1].set_xticklabels(xy_ticks)
        ax[1].set_title('$A_{p2}$', fontsize=subtitle_fontsize , weight='bold')
        cbar = fig.colorbar(im, ax=ax.ravel().tolist(), shrink=0.3, ticks=[0, 1])
        fig.suptitle('Adjacency matrices',fontsize=title_fontsize, weight='bold')
        plt.savefig(os.path.join(main_dir,'figures/article',A_filename+'_types.png'), bbox_inches='tight', dpi=dpi)
        
        A_p1 = A[:,:,:S1]
        A_p2 = A[:,:,S1:]
        fig, axs = plt.subplots(2, 5, figsize=(15, 7), constrained_layout=True)
        #fig.subplots_adjust(top=0.9)  # Add space between suptitle and subplots
        #fig.subplots_adjust(hspace=0.6)  # Add space between the first 5 subplots and the last 5 subplots
        axs = axs.ravel()
        for s in range(S1+S2):
            if s < S1:
                im = axs[s].imshow(A_p1[:,:,s], cmap=cmap)
                axs[s].set_ylabel('Nodes', fontsize=label_fontsize)
                axs[s].set_xlabel('Nodes', fontsize=label_fontsize)
            else:
                im = axs[s].imshow(A_p2[:,:,s-S1], cmap=cmap)
                axs[s].set_ylabel('Nodes', fontsize=label_fontsize)
                axs[s].set_xlabel('Nodes', fontsize=label_fontsize)

        axs[0].set_title('$A_{p1}$', fontsize=subtitle_fontsize, weight='bold')
        axs[5].set_title('$A_{p2}$', fontsize=subtitle_fontsize, weight='bold')    
        fig.suptitle('Adjacency matrices for synthetic data', fontsize=title_fontsize, weight='bold')
        cbar = fig.colorbar(im, ax=axs.ravel().tolist(), shrink=0.9, ticks=[0, 1])
        plt.savefig(os.path.join(main_dir,'figures/article',A_filename+'_all.png'), bbox_inches='tight', dpi=dpi)
    
    return A, Z, Zexp, eta_p1, eta_p2


def get_syn_nmi(exp_paths, K, Nc_type, alpha, main_dir=main_dir, dataset='synthetic'):
    
    Zexp_filename = 'Zexp_'+str(K)+'_'+str(Nc_type)+'_{:.2g}'.format(alpha)
    Z_exp = np.load(os.path.join(main_dir,'data',dataset,Zexp_filename+'.npy'))
    maxiter_gibbs = 100
    nmi_list = []
    for path in exp_paths:
        sample = np.load(os.path.join(path, 'model_sample'+str(maxiter_gibbs)+'.npy'), allow_pickle=True).item()
        Z_MAP = sample['MAP']['Z'].T
        labels_MAP = Z_MAP.argmax(axis=1)
        labels_exp = Z_exp.argmax(axis=1)
        nmi = normalized_mutual_info_score(labels_true=labels_exp, labels_pred=labels_MAP)
        nmi_list.append(nmi)
    
    return nmi_list


def boxplot_syn_nmi(df, K, ini_noc, maxiter_gibbs=100, dataset='synthetic'):
    # function for plotting boxplot of NMI(Z_MAP,Z_exp) across multiple initializations over alpha

    ## INPUT
    # df        Dataframe containing experiment overview (output from function get_exp_overview)
    # K         Original number of clusters used to generate synthetic data
    # ini_noc   Initial number of clusters used as the model's starting guess 

    ## OUTPUT
    # saved figures in folder
    
    Nc_type_list = np.unique(df.Nc_type)
    alpha_list = np.unique(df.alpha)
    #noc_list = list(set(df.noc))
    #nmi_list3 = []
    
    # Loop over Nc_type (one plot per Nc_type)
    for Nc_type in Nc_type_list:
        nmi_list2 = []
        for alpha in alpha_list:
            # compute list of experiment folder names for unique experiment for different initializations  (same Nc_type, initial noc and alpha)
            exp_folders = df[(df.K == K) & (df.Nc_type==Nc_type) & (df.alpha==alpha) & (df.noc==ini_noc)].exp_name_list.iloc[0]
            exp_paths = [os.path.join(main_dir,'results',dataset,folder) for folder in exp_folders]
            #exp_paths = get_done_exp_list(exp_paths, maxiter_gibbs=maxiter_gibbs)
            # compute list of nmi(Z_MAP,Z) across initializations (distribution across y-axis)
            nmi_list1 = get_syn_nmi(exp_paths=exp_paths, K=K, Nc_type=Nc_type, alpha=alpha) 
            # compute list of nmi_list1 across different alpha values (x-axis)
            nmi_list2.append(nmi_list1)
        # compute list of nmi_list2 for different initial noc (legends)
        #nmi_list3.append(nmi_list2) 
        
        # PLOT
        fig, ax = plt.subplots()
        bp = ax.boxplot(nmi_list2, patch_artist=True, boxprops=dict(facecolor="C0"))
        ax.set_xticklabels(alpha_list)
        ax.set_ylim([-0.1,1.1])
        ax.set_ylabel('NMI($z_{MAP}$,$z_{Exp}$)',fontsize=label_fontsize)
        #ax.set_xlabel('alpha', fontsize=label_fontsize)
        ax.set_xlabel('\u03B1', fontsize=label_fontsize)
        ax.yaxis.grid(True)
        ax.set_title('Exp: K='+str(K)+'_'+str(Nc_type), fontsize=12, weight='bold')
    
        plt.savefig(os.path.join(main_dir,'figures','article','syn_bp_nmi_'+str(K)+'_'+str(Nc_type)+'.png'), bbox_inches='tight', dpi=dpi)
#return nmi_list1, nmi_list2       

    
def get_done_exp_list(exp_paths, maxiter_gibbs):
    # get the list of experiments which haev finished runnning (done experiments)
    exist_mask = [os.path.exists(os.path.join(path, 'model_sample'+str(maxiter_gibbs)+'.npy')) for path in exp_paths]
    exp_paths = [path for path, boolean in zip(exp_paths, exist_mask) if boolean] # only using experiments which are done running 
    return exp_paths


def get_stats(exp_folders, par, maxiter_gibbs, dataset='hcp'):
    
    MAPpar_list = []
    par_list = []
    min_maxiter = np.inf
    for folder in exp_folders:
        path = os.path.join(main_dir,'results',dataset,folder)
        sample = np.load(os.path.join(path, 'model_sample'+str(maxiter_gibbs)+'.npy'), allow_pickle=True).item()
        MAPpar = sample['MAP'][par]
        par_array = sample[par]
        sample_maxiter = len(par_array)
        min_maxiter = min(min_maxiter, sample_maxiter)
        MAPpar_list.append(MAPpar)
        par_list.append(par_array[:min_maxiter])

    # Pad or truncate arrays to have consistent shape
    par_list = [np.pad(arr, (0, min_maxiter - len(arr)), mode='constant') if len(arr) < min_maxiter else arr[:min_maxiter] for arr in par_list]

    # Compute mean par at each iteration across all experiments
    mean_par = np.mean(par_list, axis=0)
    # Compute min and max par at each iteration
    min_par = np.min(par_list, axis=0)
    max_par = np.max(par_list, axis=0)
    
    return MAPpar_list, par_list, mean_par, min_par, max_par


def plot_par(df, par, miniter_gibbs=None, dataset='hcp', main_dir=main_dir, label_fontsize=label_fontsize, subtitle_fontsize=subtitle_fontsize, title_fontsize=title_fontsize, fig_name=None):
    
    # Input:  
    # dataset: 'hcp'
    # df: dataframe with experiment overview
    # par: parameter to plot as a function of Gibbs iterations, e.g. 'logP' or 'noc'
    # miniter_gibbs: minimum Gibbs iteration to plot
    # maxiter_gibbs: maximum Gibbs iteration to plot
    
    # Output: plot of parameter as a function of Gibbs iterations
    
    plt.figure(figsize=(8,6))
    cmap = plt.get_cmap('tab20')
    label_dict = {'logP_A': 'log P$(A|z)$', 'logP_Z': 'log P$(z)$', 'logP': 'log P$(z,A)$', 'pairwise_nmi': "NMI$(z,z\')$"}
    for idx, row in df.iterrows():
        exp_folders = row.exp_name_list
        noc = row.noc
        exp_paths = [os.path.join(main_dir,'results',dataset,folder) for folder in exp_folders]
        if noc < 100:
            maxiter_gibbs = 100
        else: # also include where noc=100 (they only ran 30 iterations)
            maxiter_gibbs = 30
        exp_paths = get_done_exp_list(exp_paths, maxiter_gibbs)
        
        if len(exp_paths) > 0: 
            MAPpar_list, par_list, mean_par, min_par, max_par = get_stats(exp_paths, par, maxiter_gibbs)
            iters = range(len(mean_par))
            
            if miniter_gibbs is None:
                miniter_gibbs = iters[0]
            if maxiter_gibbs is None:
                maxiter_gibbs = iters[-1]
            color = cmap(idx)
            plt.plot(iters[miniter_gibbs:maxiter_gibbs], mean_par[miniter_gibbs:maxiter_gibbs], label=noc, color=color)
            plt.fill_between(iters[miniter_gibbs:maxiter_gibbs], min_par[miniter_gibbs:maxiter_gibbs], max_par[miniter_gibbs:maxiter_gibbs], alpha=0.5, color=color)
    
    #plt.title(par, fontsize=title_fontsize, weight='bold')
    plt.ylabel(label_dict[par], fontsize=label_fontsize)
    plt.xlabel('Model iterations', fontsize=label_fontsize)
    plt.legend(loc='upper right',fontsize=legend_fontsize, fancybox=True, shadow=True, bbox_to_anchor=(1.15, 0.85))
    if fig_name is not None:
        plt.savefig(os.path.join(main_dir,'figures/article',dataset+'_'+fig_name+'.png'), bbox_inches='tight', dpi=dpi) 
    else:
        plt.savefig(os.path.join(main_dir,'figures/article',dataset+'_plot_'+par+'.png'), bbox_inches='tight', dpi=dpi)  


def get_MAP_parlist(exp_folders, noc, par, dataset='hcp'): # this function might be unnecessary since we can get MAP_par_list from get_stats function
    exp_paths = [os.path.join(main_dir,'results',dataset,folder) for folder in exp_folders]
    if noc < 100:
        maxiter_gibbs = 100
    else: # also including where noc=100 (they only ran 30 iterations)
        maxiter_gibbs = 30
    exp_paths = get_done_exp_list(exp_paths, maxiter_gibbs)

    MAPpar_list = []
    for path in exp_paths:
        sample = np.load(os.path.join(path, 'model_sample'+str(maxiter_gibbs)+'.npy'), allow_pickle=True).item()
        MAPpar = sample['MAP'][par]
        MAPpar_list.append(MAPpar)
    return MAPpar_list


def generate_number_pairs(max_num):
    pairs = []
    for i in range(max_num):
        for j in range(i + 1, max_num):
            pairs.append([i, j])
    return pairs


def get_pairwise_nmi(exp_folders, noc, main_dir=main_dir, dataset='hcp'):
    # compute pairwise nmi for hcp data
    
    exp_paths = [os.path.join(main_dir,'results',dataset,folder) for folder in exp_folders]
    if noc < 100:
        maxiter_gibbs = 100
    else: # also include where noc=100 (they only ran 30 iterations)
        maxiter_gibbs = 30
    exp_paths = get_done_exp_list(exp_paths, maxiter_gibbs) # experiments that are done running (some are still not finished)

    n_exp = len(exp_paths)
    pairs = generate_number_pairs(n_exp)
    nmi_list = []
    for pair in pairs:
        sample0 = np.load(os.path.join(exp_paths[pair[0]], 'model_sample'+str(maxiter_gibbs)+'.npy'), allow_pickle=True).item()
        sample1 = np.load(os.path.join(exp_paths[pair[1]], 'model_sample'+str(maxiter_gibbs)+'.npy'), allow_pickle=True).item()
        Z0 = sample0['MAP']['Z'].T
        Z1 = sample1['MAP']['Z'].T
        labels0 = Z0.argmax(axis=1)
        labels1 = Z1.argmax(axis=1)
        nmi = normalized_mutual_info_score(labels_true=labels0, labels_pred=labels1)
        nmi_list.append(nmi)
    
    return nmi_list


def boxplot_par_over_ininoc(df, par):
    # function for plotting boxplot of a given parameter across multiple initializations over initial noc

    ## INPUT
    # df    Dataframe containing experiment overview (output from function get_exp_overview)
    # par   Parameter to plot ('logP', 'logP_A', 'logP_Z' or 'noc') or 'pairwise_nmi'
    
    ## OUTPUT
    # saved figures in folder

    noc_list = np.unique(df.noc)
    label_dict = {'logP_A': 'log P$(A|z)$', 'logP_Z': 'log P$(z)$', 'logP': 'log P$(z,A)$', 'pairwise_nmi': "NMI$(z,z\')$"}
    # Loop over and Nc_type (one plot per Nc_type)
    par_list2 = []
    for noc in noc_list:
        # compute list of experiment folder names for unique experiment for different initializations 
        exp_folders = df[(df.noc==noc)].exp_name_list.iloc[0]
        # compute list of respective parameter values across initializations (distribution across y-axis)
        if par == 'pairwise_nmi':
            par_list1 = get_pairwise_nmi(exp_folders=exp_folders, noc=noc) 
        else:
            par_list1 = get_MAP_parlist(exp_folders=exp_folders, noc=noc, par=par)
        # compute list of par_list1 across different initial noc (x-axis)
        #if len(par_list1) > 0:
        par_list2.append(par_list1)
    
    # PLOT
    fig, ax = plt.subplots()
    bp = ax.boxplot(par_list2, patch_artist=True, boxprops=dict(facecolor="C0"))
    ax.set_xticklabels(noc_list)
    ax.set_xlabel('Initial K', fontsize=label_fontsize)
    ax.yaxis.grid(True)
    
    if par == 'pairwise_nmi':
        ax.set_ylabel(label_dict[par],fontsize=label_fontsize)
        #ax.set_title('Pairwise NMI of $Z_{MAP}$ for different initializations', fontsize=12, weight='bold')
        ax.set_ylim([-0.1,1.1])
        plt.savefig(os.path.join(main_dir,'figures','article','hcp_bp_pairwise_nmi.png'), bbox_inches='tight', dpi=dpi)
    else:
        #ax.set_ylabel('MAP '+par,fontsize=label_fontsize)
        ax.set_ylabel(label_dict[par],fontsize=label_fontsize)
        #ax.set_title('MAP '+ par+' for different initializations', fontsize=12, weight='bold')
        plt.savefig(os.path.join(main_dir,'figures','article','hcp_bp_MAP_'+par+'.png'), bbox_inches='tight', dpi=dpi)
#return par_list1, par_list2   


def plot_par_over_ininoc(df, pars):
    # function for plotting boxplot of a given parameter across multiple initializations over initial noc

    ## INPUT
    # df    Dataframe containing experiment overview (output from function get_exp_overview)
    # par   Parameter to plot ('logP', 'logP_A', 'logP_Z' or 'noc') or 'pairwise_nmi'
    
    ## OUTPUT
    # saved figures in folder

    noc_list = np.unique(df.noc)
    
    plt.figure(figsize=(8,6))
    
    label_dict = {'logP_A': 'log P$(A|z)$', 'logP_Z': 'log P$(z)$', 'logP': 'log P$(z,A)$', 'pairwise_nmi': "NMI$(z,z\')$"}
    for par in pars:
        # Loop over Nc_type (one plot per Nc_type)
        mean_par_list = []
        min_par_list = []
        max_par_list = []
        for noc in noc_list:
            # compute list of experiment folder names for unique experiment for different initializations  (same Nc_type, initial noc and alpha)
            exp_folders = df[(df.noc==noc)].exp_name_list.iloc[0]
            # compute list of respective parameter values across initializations (distribution across y-axis)
            if par == 'pairwise_nmi':
                par_list1 = get_pairwise_nmi(exp_folders=exp_folders, noc=noc) 
            else:
                par_list1 = get_MAP_parlist(exp_folders=exp_folders, noc=noc, par=par)
            # compute list of par_list1 across different initial noc (x-axis)
            if len(par_list1) > 0:
                mean_par = np.mean(par_list1, axis=0)
                min_par = np.min(par_list1, axis=0)
                max_par = np.max(par_list1, axis=0)
                mean_par_list.append(mean_par)
                min_par_list.append(min_par)
                max_par_list.append(max_par)
        
        # PLOT
        plt.plot(noc_list[:len(mean_par_list)], mean_par_list, label=label_dict[par], marker='o')#, color='red')
        plt.fill_between(noc_list[:len(mean_par_list)], min_par_list, max_par_list, alpha=0.5)#, color=color)
        
    plt.xlabel('Initial $K$', fontsize=label_fontsize)
   
    if par == 'pairwise_nmi':
        plt.ylabel(label_dict[par],fontsize=label_fontsize)
        plt.ylim([-0.1,1.1])
        #plt.title('Pairwise NMI of $Z_{MAP}$ for different initializations', fontsize=title_fontsize, weight='bold')
        plt.savefig(os.path.join(main_dir,'figures','article','hcp_plot_pairwise_nmi.png'), bbox_inches='tight', dpi=dpi)
    else:
        plt.ylabel('MAP log prob.', fontsize=label_fontsize)
        #plt.title('MAP value for different initializations', fontsize=title_fontsize, weight='bold')
        #plt.legend(loc='upper right',fontsize='small', fancybox=True, shadow=True, bbox_to_anchor=(1.15, 0.85))
        plt.legend(loc='center right',fontsize=legend_fontsize, fancybox=True, shadow=True)
        plt.savefig(os.path.join(main_dir,'figures','article','hcp_plot_MAP_pars.png'), bbox_inches='tight', dpi=dpi)
     
        
def plot_eta(dataset, eta, exp_name_title=None, main_dir=main_dir, label_fontsize=label_fontsize, subtitle_fontsize=subtitle_fontsize, title_fontsize=title_fontsize, cmap_color=cmap_color):
    if dataset == 'hcp' or dataset == 'synthetic':
        S1 = 5 
        S2 = 5
        # note: for mri, the first 5 graphs are functional and last 5 graphs structural 
    else:
        print('unknown dataset')
    
    eta_type1 = eta[:,:,:S1] 
    eta_type2 = eta[:,:,S1:] 
    
    fig, axs = plt.subplots(2, 5, figsize=(15, 7), constrained_layout=True)
    axs = axs.ravel()
    cmap = cmap_color
    
    K = eta.shape[0]
    #max_val = np.max(eta)
    xy_ticks = range(0, K + 1, 1)

    for s in range(10):
        if s < 5:
            im = axs[s].imshow(eta_type1[:,:,s], cmap=cmap, extent=[0,K,K,0])#, vmin=0, vmax=max_val)
            axs[s].set_ylabel('Cluster', fontsize=label_fontsize)
            axs[s].set_xlabel('Cluster', fontsize=label_fontsize)
            axs[s].set_yticks(xy_ticks)
            axs[s].set_yticklabels(xy_ticks)
            axs[s].set_xticks(xy_ticks)
            axs[s].set_xticklabels(xy_ticks)
        else:
            im = axs[s].imshow(eta_type2[:,:,s-S1], cmap=cmap, extent=[0,K,K,0])#, vmin=0, vmax=max_val)
            axs[s].set_ylabel('Cluster', fontsize=label_fontsize)
            axs[s].set_xlabel('Cluster', fontsize=label_fontsize)
            axs[s].set_yticks(xy_ticks)
            axs[s].set_yticklabels(xy_ticks)
            axs[s].set_xticks(xy_ticks)
            axs[s].set_xticklabels(xy_ticks)

    if dataset == 'hcp':
        axs[0].set_title('Functional', fontsize=subtitle_fontsize, weight='bold')
        axs[5].set_title('Structural', fontsize=subtitle_fontsize, weight='bold')
    elif dataset == 'synthetic':
        axs[0].set_title('Type 1', fontsize=subtitle_fontsize, weight='bold')
        axs[5].set_title('Type 2', fontsize=subtitle_fontsize, weight='bold')
    else: 
        print('unknown dataset')
    fig.suptitle('Cluster-link probability matrices,\n Experiment: ' + exp_name_title, fontsize=title_fontsize, weight='bold')
    cbar = fig.colorbar(im, ax=axs.ravel().tolist(), shrink=0.95)
    plt.savefig(os.path.join(main_dir,'figures','article',dataset+'_eta_types_'+str(K)+'.png'), bbox_inches='tight', dpi=dpi)    
   
   
def plot_ZMAP(Z, dataset):
    noc = Z.shape[0]
    fig, ax = plt.subplots()
    cmap_binary = ListedColormap(['w', 'k']) #ListedColormap(['k', 'w']) 
    im = ax.imshow(Z.T, interpolation='nearest', aspect='auto', cmap=cmap_binary, extent=(0, Z.shape[0], 0, Z.shape[1]))
    ax.set_title('$z_{MAP}$', fontsize=title_fontsize, weight='bold')
    plt.xlabel('Cluster', fontsize=label_fontsize)
    plt.ylabel('Node', fontsize=label_fontsize)
    plt.setp(ax, xticks=range(len(Z)))
    cbar = fig.colorbar(im, ax=ax, shrink=0.7, ticks=[0,1])
    plt.savefig(os.path.join(main_dir,'figures','article',dataset+'_Z_'+str(noc)+'.png'), bbox_inches='tight', dpi=dpi)
    

def center_crop(im, crop_shape):
    new_width, new_height = crop_shape
    width, height = im.size   # Get dimensions

    left = (width - new_width)/2
    top = (height - new_height)/2
    right = (width + new_width)/2
    bottom = (height + new_height)/2

    # Crop the center of the image
    im_crop = im.crop((left, top, right, bottom))
    return im_crop


def merge_images(im1,im2,im3, crop_shape, paste_shape, merged_im_title):
    # merge images from different views into one (brain icons for each cluster in connectivity plot)

    # crop_shape = (width, height)
    im1 = center_crop(im1, crop_shape)
    im2 = center_crop(im2, crop_shape)
    im3 = center_crop(im3, (crop_shape[0]+20,crop_shape[1]+20))
    
    im_size = im3.size
    new_im = Image.new('RGB',(2*im_size[0], im_size[1]), color=(255,255,255))
    new_im.paste(im1,(0,0))
    new_im.paste(im2,(im_size[0],0))
    new_im_size = new_im.size
    
    newnew_image = Image.new('RGB',(new_im_size[0], 2*new_im_size[1]), color=(255,255,255))
    newnew_image.paste(new_im,(0,0))
    newnew_image.paste(im3,paste_shape)
    newnew_image.save('figures/article/'+merged_im_title, 'PNG')
    return newnew_image

def compute_Glasser_A(filename):
    # Compute new adjacency matrix with density estimated using Glasser atlas parcellation
    ## INPUT
    # filename          filename of dmri or fmri graph from HCP data e.g. 'dmri_sparse1.npz' or 'fmri_sparse1.npz' (dimension 59412x59412)
    
    ## OUTPUT
    # Glasser_A         new adjacency matrix (dimension 360x360)
    

    # load Glasser parcellation
    parcels_L = loadmat(os.path.join(main_dir,'data','hcp','Glasser_L.mat'))['parcels'].flatten().astype(np.int32)
    parcels_R = loadmat(os.path.join(main_dir,'data','hcp','Glasser_R.mat'))['parcels'].flatten().astype(np.int32)
    # NOTICE THAT RIGHT PARCELS ARE SHIFTED, SO WE HAVE 360 UNIQUE LABELS
    z = np.append(parcels_L, parcels_R + np.max(parcels_L)) # cluster labels z 

    # load original graph
    data_path = os.path.join(main_dir, 'data','hcp')
    A = load_npz(os.path.join(data_path, filename)).astype(dtype=np.int32)
    A = triu(A,1)

    N = len(z)
    Z = csr_matrix((np.ones(N), (z-1, np.arange(N))), shape=(np.max(z), N)) # Note: z - 1 because python is 0-indexed and labels start at 1
    sumZ = Z.sum(axis=1)
    Ntot = np.asarray(sumZ @ sumZ.T - Z @ Z.T)
    Ntot = Ntot - 0.5 * np.diag(np.diag(Ntot))
    Nlink = (Z @ A @ Z.T).toarray()
    Nlink = Nlink + Nlink.T
    Nlink = Nlink - 0.5 * np.diag(np.diag(Nlink))
    etaD = Nlink/Ntot # this corresponds to the graph with density computed wrt. Glasser atlas/parcellation
    np.save(os.path.join(data_path,'Glasser_A_'+filename.split('.')[0]+'.npy'),etaD)
    return etaD


def get_best_run(df, noc, dataset='hcp'):
    # get name of experiment/run with highest MAP estimate across random runs! 
    exp_folders = df[(df.noc==noc)].exp_name_list.iloc[0]
    exp_paths = [os.path.join(main_dir,'results',dataset,folder) for folder in exp_folders]
    if noc < 100:
        maxiter_gibbs = 100
    else: # also including where noc=100 (they only ran 30 iterations)
        maxiter_gibbs = 30
    exp_paths = get_done_exp_list(exp_paths, maxiter_gibbs)

    MAPpar_list = []
    for path in exp_paths:
        sample = np.load(os.path.join(path, 'model_sample'+str(maxiter_gibbs)+'.npy'), allow_pickle=True).item()
        MAPpar = sample['MAP']['logP']
        MAPpar_list.append(MAPpar)
        
    best_run_exp_folder = exp_folders[np.argmax(MAPpar_list)]
    return best_run_exp_folder


def plot_eta_metric_matrix(eta, metric, subset=None):
    noc = eta.shape[0]
    # computing subset
    if subset == 'fmri':
        eta_set = eta[:,:,:5]
        cmap = plt.cm.Reds
    elif subset == 'dmri':
        eta_set = eta[:,:,5:]
        cmap = plt.cm.Blues
    else:
        print('Not using subset')
        eta_set = eta

    # computing metric
    if metric == 'std':
        eta_metric = np.std(eta_set, axis=2)
    elif metric == 'KL_div':  # KL divergence = relative entropy
        eta_metric = entropy(eta_set, np.ones(eta_set.shape), axis=2)  # relative to a uniform distribution
    elif metric == 'mean':
        eta_metric = np.mean(eta_set, axis=2)
    else:
        print('Not using metric')
    
    plt.figure(figsize=(4,4))
    plt.imshow(eta_metric, cmap = cmap)
    plt.colorbar()
    plt.xticks([])
    plt.yticks([])
    title_dict = {'std': 'Std. of $\eta$', 'KL_div': 'KL div. of $\eta$', 'mean': 'Mean of $\eta$'}
    if subset is not None:
        plt.title(title_dict[metric] + ' - ' + subset, fontsize = subtitle_fontsize, weight='bold')
        plt.savefig(os.path.join(main_dir, 'figures/article/eta_'+metric+'_mat_'+ str(noc) + '_' + subset + '.png'), bbox_inches='tight', dpi=dpi)
    else:
        plt.title(title_dict[metric] + ' - All', fontsize = subtitle_fontsize, weight='bold')
        plt.savefig(os.path.join(main_dir, 'figures/article/eta_'+metric+'_mat_'+ str(noc) + '_all.png'), bbox_inches='tight', dpi=dpi)


def get_curved_line(start, end, direction, shift=0.1, num_points=100):
    # get curved line using Bezier lines 
    '''
    # Example usage
    start_point = (1,0)
    end_point = (1,1)

    x_curve_up, y_curve_up = get_curved_line(start_point, end_point, direction='up')
    x_curve_down, y_curve_down = get_curved_line(start_point, end_point, direction='down')

    plt.plot(x_curve_up, y_curve_up, linestyle='-', label='Bézier Curve')
    plt.plot(x_curve_down, y_curve_down, linestyle='-', label='Bézier Curve')
    '''
    
    # middle point should be computed differently depending on whether the line should curve upwards (function/red) or downwards (structure/blue)
    if start[0]==end[0]:
        mid_y = (start[1]+end[1])/2
        if direction == 'up':
            mid_x = np.max([start[0],end[0]])+shift
        elif direction == 'down':
            mid_x = np.min([start[0],end[0]])-shift
    else:
        mid_x = (start[0]+end[0])/2
        if direction == 'up':
            mid_y = np.max([start[1],end[1]])+shift
        elif direction == 'down':
            mid_y = np.min([start[1],end[1]])-shift
    middle = (mid_x,mid_y)
    
    t = np.linspace(0, 1, num_points)

    # Bézier curve formula
    arc_x = (1 - t)**2 * start[0] + 2 * (1 - t) * t * middle[0] + t**2 * end[0]
    arc_y = (1 - t)**2 * start[1] + 2 * (1 - t) * t * middle[1] + t**2 * end[1]
    return arc_x, arc_y


def plot_eta_graph(eta, top_links=False, plot_function=True, plot_structure=True, main_dir=main_dir, label_fontsize=label_fontsize, subtitle_fontsize=subtitle_fontsize, title_fontsize=title_fontsize):
    ''' Plots the mean eta (cluster link-probabilities) across functional (red) and structural (blue) graphs with brain icons at each node'''
    
    K = eta.shape[0]

    # Define the matrices eta_mean_s and eta_mean_f
    eta_mean_f = np.mean(eta[:,:,:5],axis=2) # mean eta over functional graphs
    eta_mean_s = np.mean(eta[:,:,5:],axis=2) # mean eta over structural graphs

    vmin = 0#np.min([eta_mean_f, eta_mean_s])
    vmax = 0.2#np.max([eta_mean_f, eta_mean_s])

    if top_links:
        print('thesholding links: showing top 1%')
        thres_f = np.percentile(eta_mean_f,99)
        eta_mean_f[np.where(eta_mean_f < thres_f)] = 0
        thres_s = np.percentile(eta_mean_s,99)
        eta_mean_s[np.where(eta_mean_s < thres_s)] = 0
        
    # Define the colormap for eta_mean_s and eta_mean_f
    cmap_s = plt.cm.Blues
    cmap_f = plt.cm.Reds
    
    sm_s = plt.cm.ScalarMappable(cmap=cmap_s, norm=plt.Normalize(vmin=vmin, vmax=vmax))
    sm_s.set_array([])
    sm_f = plt.cm.ScalarMappable(cmap=cmap_f, norm=plt.Normalize(vmin=vmin, vmax=vmax))
    sm_f.set_array([])


    # Define the positions of the nodes based on the number of nodes
    if K == 2:
        # link linewidth
        lw_inter = 6
        lw_intra = 6
        # node positions
        pos = np.array([[0, 0], [0.5, 0]])
        # brain images params
        imsize = 0.7
        shift = 0.3
        shift_pos = np.array([[pos[0][0]-shift, pos[0][1]], [pos[1][0]+shift, pos[1][1]]])
        fig_size = (6, 8)
        # colorbar params
        pad_s = 0.2
        pad_f = 0.3
    elif K == 3:
        # link linewidth
        lw_inter = 6
        lw_intra = 6
        # node positions
        pos = np.array([[0, 0], [0.5, 0], [0.25, 0.4]])
        # brain images params
        imsize = 0.7
        shift = 0.3
        shift_pos = np.array([[pos[0][0]-0.2, pos[0][1]-0.1], [pos[1][0]+0.2, pos[1][1]-0.1], [pos[2][0], pos[2][1]+shift]])
        fig_size = (8, 6)
        # colorbar params
        pad_s = 0.2 
        pad_f = 0.3
    elif K == 4:
        # link linewidth
        lw_inter = 4
        lw_intra = 6
        # node positions
        pos = np.array([[0, 0], [0.3, 0], [0.3, 0.3], [0, 0.3]])
        # brain images params
        imsize = 0.7
        shift = 0.19
        shift_pos = np.array([[pos[0][0]-shift, pos[0][1]-shift], [pos[1][0]+shift, pos[1][1]-shift], [pos[2][0]+shift, pos[2][1]+shift], [pos[3][0]-shift, pos[3][1]+shift]])
        fig_size = (4, 4)
        # colorbar params
        pad_s = 0.2
        pad_f = 0.3
    else:
        # link linewidth
        lw_inter = 3
        lw_intra = 6
        # node positions
        pos = np.zeros((K, 2))
        for i in range(K):
            angle = 2 * np.pi * i / K
            x = np.cos(angle)
            y = np.sin(angle)
            pos[i] = [x, y]
        fig_size = (K, K)
        # colorbar params
        pad_s = 0.2
        pad_f = 0.3
        # brain images params
        shift = 0.25
        imsize = 0.1
    
    # Plot eta mean matrices
    ticks = [vmin,0.1,vmax]
    fig_f, ax_f = plt.subplots(figsize=(4,4))
    ax_f.imshow(eta_mean_f, cmap = cmap_f)
    cbar_f = plt.colorbar(sm_f, ax=ax_f, shrink=0.8, ticks=ticks)
    ax_f.set_title('Mean of $\eta$ - Functional',fontsize = 14, weight='bold')
    ax_f.set_xticks([])
    ax_f.set_yticks([])
    cbar_f.ax.set_yticklabels(ticks)  
    
    fig_s, ax_s = plt.subplots(figsize=(4,4))
    ax_s.imshow(eta_mean_s, cmap = cmap_s)
    cbar_s = plt.colorbar(sm_s, ax=ax_s, shrink=0.8,ticks=ticks)
    ax_s.set_title('Mean of $\eta$ - Structural',fontsize = 14, weight='bold')
    ax_s.set_xticks([])
    ax_s.set_yticks([])
    cbar_s.ax.set_yticklabels(ticks)  
  
    # Plot the graph with nodes and links
    fig, ax = plt.subplots(figsize=fig_size)
    ax.set_aspect('equal')
    ax.axis('off')

    triu_indices = np.triu_indices(K, k=1) # due to symmetric eta, we only plot the upper triangular values
    for i, j in zip(triu_indices[0], triu_indices[1]):
        # Plot the curved link lines
        arc_x1, arc_y1 = get_curved_line(pos[i], pos[j], direction='up')
        arc_x2, arc_y2 = get_curved_line(pos[i], pos[j], direction='down')
        if plot_function & (eta_mean_f[i,j] > 0):
            ax.plot(arc_x1, arc_y1, color=sm_f.to_rgba(eta_mean_f[i, j]), linewidth=lw_inter, zorder=0)
        if plot_structure & (eta_mean_s[i,j] > 0):
            ax.plot(arc_x2, arc_y2, color=sm_s.to_rgba(eta_mean_s[i, j]), linewidth=lw_inter, zorder=1)
        
    # Plot the nodes
    ax.scatter(pos[:, 0], pos[:, 1], s=100, color='grey', zorder=2)

    # Add colorbars 
    #cbar_s = plt.colorbar(sm_s, ax=ax, shrink=0.8, pad=pad_s)
    #cbar_f = plt.colorbar(sm_f, ax=ax, shrink=0.8, pad=pad_f)

    # Add node labels
    for i in range(K):
        ax.text(pos[i, 0], pos[i, 1], str(i), fontsize=8, ha='center', va='center',zorder=3)

    # plot self-loop on brain icons and save 
    #node_labels = np.argmax(Z, axis=0) + 1
    #label_list = np.unique(node_labels)
    images = []
    for i in range(K):
        label = i+1
        im = Image.open('figures/article/brain_merged_' + str(K) + '_' + str(label) + '.png')
        fig1,ax1 = plt.subplots(1)
        ax1.imshow(im)
        width_e = im.size[0]+100
        height_e = im.size[1]+100
        #patch = Ellipse((330,250), width=width_e, height=height_e, fill=False, color='green', linewidth=2)
        patch1 = Arc((330,250), width=width_e, height=height_e, theta1=0, theta2=180, fill=False, color=sm_f.to_rgba(eta_mean_f[i, i]), linewidth=lw_intra)
        patch2 = Arc((330,250), width=width_e, height=height_e, theta1=180, theta2=360, fill=False, color=sm_s.to_rgba(eta_mean_s[i, i]), linewidth=lw_intra)
        if (eta_mean_f[i,i] > 0):
            ax1.add_patch(patch1)
        if (eta_mean_s[i,i] > 0):
            ax1.add_patch(patch2)
        ax1.set_xlim([-60, 710])
        ax1.set_ylim([580, -80])
        ax1.axis('off')
        plt.savefig(os.path.join(main_dir,'figures/article','brain_merged_'+str(K)+'_'+str(label)+'_loop.png'), bbox_inches='tight')
        plt.close()
        im_loop = mpimg.imread('figures/article/brain_merged_' + str(K) + '_' + str(label) + '_loop.png')
        images.append(im_loop)

    # Displaying image icons on networkx nodes
    trans = ax.transData.transform
    trans2 = fig.transFigure.inverted().transform

    for i in range(K):
        if K < 5:
            shift_x, shift_y = shift_pos[i]
        else:
            (x, y) = pos[i]
            angle = 2 * np.pi * i / K
            shift_x = x + shift * np.cos(angle)
            shift_y = y + shift * np.sin(angle)
        xx, yy = trans((shift_x, shift_y))  # figure coordinates
        xa, ya = trans2((xx, yy))  # axes coordinates
        a = plt.axes([xa - imsize/2.0, ya - imsize/2.0, imsize, imsize])
        a.imshow(images[i])
        a.set_aspect('equal')
        a.axis('off')

    #fig.show()
    if top_links:
        fig_f.savefig(os.path.join(main_dir, 'figures/article/eta_mean_fmat_'+ str(K)+'_toplinks.png'), bbox_inches='tight', dpi=dpi)
        fig_s.savefig(os.path.join(main_dir, 'figures/article/eta_mean_smat_'+ str(K)+'_toplinks.png'), bbox_inches='tight', dpi=dpi)
        fig.savefig(os.path.join(main_dir, 'figures/article/eta_mean_graph_'+ str(K)+'_toplinks.png'), bbox_inches='tight', dpi=dpi)
    else:
        fig.savefig(os.path.join(main_dir, 'figures/article/eta_mean_graph_'+ str(K)+'.png'), bbox_inches='tight', dpi=dpi)
        fig_f.savefig(os.path.join(main_dir, 'figures/article/eta_mean_fmat_'+ str(K)+'.png'), bbox_inches='tight', dpi=dpi)
        fig_s.savefig(os.path.join(main_dir, 'figures/article/eta_mean_smat_'+ str(K)+'.png'), bbox_inches='tight', dpi=dpi)
