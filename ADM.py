import time
t0=time.time()
print("importing packs")
import yaml
from packs.running.initial_mesh_properties import initial_mesh
from packs.pressure_solver.fine_scale_tpfa import FineScaleTpfaPressureSolver
from packs.multiscale.multilevel.multilevel_operators import MultilevelOperators
from packs.directories import data_loaded
import scipy.sparse as sp
import numpy as np
import time
from pymoab import types
from scipy.sparse import csc_matrix, find, csgraph
# from packs.adm.adm_method import AdmMethod
from packs.adm.non_uniform.adm_method_non_nested import AdmNonNested
from matplotlib.colors import LinearSegmentedColormap
print("time to import packs: {} seconds".format(time.time()-t0))
'''
def get_gids_and_primal_id(gids, primal_ids):
    gids2 = np.unique(gids)
    primal_ids2 = []
    for i in gids2:
        primal_id = np.unique(primal_ids[gids==i])
        if len(primal_id) > 1:
            raise ValueError('erro get_gids_and_primal_id')
        primal_ids2.append(primal_id[0])
    primal_ids2 = np.array(primal_ids2)
    return gids2, primal_ids2'''

def mostrar(i, data_impress, M, op1, rest1):
    l0 = np.concatenate(op1[:,i].toarray())
    el0 = np.concatenate(rest1[i].toarray())
    data_impress['verif_po'] = l0
    data_impress['verif_rest'] = el0
    rr = set(np.where(l0>0)[0])
    rr2 = set(np.where(el0>0)[0])
    if rr & rr2 != rr2:
        import pdb; pdb.set_trace()

def mostrar_2(i, data_impress, M, op, rest, gid0, gid_coarse1, gid_coarse2):
    l0 = np.concatenate(op[:,i].toarray())
    el0 = np.concatenate(rest[i].toarray())
    el2 = np.zeros(len(gid0))
    l2 = el2.copy()
    cont = 0
    for fid, val in enumerate(el0):
        if val == 0:
            cont += 1
            continue
        else:
            el2[gid_coarse1==fid] = np.ones(len(el2[gid_coarse1==fid]))

    for fid, val in enumerate(l0):
        if val == 0:
            continue
        n = len(gid_coarse1[gid_coarse1==fid])

        l2[gid_coarse1==fid] = np.repeat(val, n)

    data_impress['verif_po'] = l2
    data_impress['verif_rest'] = el2
    data_impress.update_variables_to_mesh(['verif_po', 'verif_rest'])
    # M.core.print(file='test_'+ str(0), extension='.vtk', config_input='input_cards/print_settings0.yml')
    # import pdb; pdb.set_trace()

# def dados_unitarios(data_impress):
    data_impress['hs'] = np.ones(len(data_impress['hs'])*3).reshape([len(data_impress['hs']), 3])
    data_impress['volume'] = np.ones(len(data_impress['volume']))
    data_impress['area'] = np.ones(len(data_impress['area']))
    data_impress['permeability'] = np.ones(data_impress['permeability'].shape)
    data_impress['k_harm'] = np.ones(len(data_impress['k_harm']))
    data_impress['dist_cent'] = np.ones(len(data_impress['dist_cent']))
    data_impress['transmissibility'] = np.ones(len(data_impress['transmissibility']))
    data_impress['pretransmissibility'] = data_impress['transmissibility'].copy()
    data_impress.export_to_npz()

# def plot_operator(OP_AMS, v):
#     vertices = elements_lv0['volumes'][data_impress['DUAL_1']==3]
#     tags_ams = []
#     for i, v in enumerate(vertices):
#         primal_id = data_impress['GID_1'][v]
#         corresp = data_impress['ADM_COARSE_ID_LEVEL_1'][v]
#         tags_ams.append(M.core.mb.tag_get_handle("OP_AMS_"+str(i), 1, types.MB_TYPE_DOUBLE, types.MB_TAG_SPARSE, True))
#         fb_ams = OP_AMS[:, primal_id].toarray()
#         # fb_adm = OP_ADM[:, corresp].toarray()
#         M.core.mb.tag_set_data(tags_ams[i], M.core.all_volumes, fb_ams)

def get_coupled_dual_volumes(mlo, neta_lim=0.0, ind=0):
    OP_AMS=mlo['prolongation_level_1']
    OR_AMS=mlo['restriction_level_1']
    Tc=OR_AMS*tpfa_solver['Tini']*OP_AMS
    Tc2=Tc.copy()
    Tc2.setdiag(0)
    DTc=1/np.array(Tc[range(Tc.shape[0]),range(Tc.shape[0])])[0]
    if (DTc>0).sum()>0 and abs(Tc[DTc>0].sum())<0.01:
        print((DTc>0).sum(),"diagonais positivas !!!!!!!!!!!")
        import pdb; pdb.set_trace()
        DTc[DTc>0]=-abs(DTc).max()

    lines=np.arange(Tc.shape[0])
    dia=csc_matrix((DTc,(lines,lines)),shape=Tc.shape)
    netas=dia*Tc2
    fn=find(netas)

    # import pdb; pdb.set_trace()
    superates_tol=fn[2]>neta_lim
    # import pdb; pdb.set_trace()
    nsp=fn[2][superates_tol]
    i=fn[1][superates_tol]
    j=fn[0][superates_tol]

    internal_faces=M.faces.internal
    adjs=M.faces.bridge_adjacencies(internal_faces,2,3)
    adjs0=adjs[:,0]
    adjs1=adjs[:,1]
    ii=data_impress['GID_1'][adjs0]
    jj=data_impress['GID_1'][adjs1]
    positives=fn[2]>0.0
    nsp_all=fn[2][positives]
    i_all=fn[1][positives]
    j_all=fn[0][positives]
    for k in range(len(nsp_all)):
        _non = (ii==i_all[k]) & (jj==j_all[k]) | (ii==j_all[k]) & (jj==i_all[k])
        ad0=adjs0[_non]
        ad1=adjs1[_non]
        neta_p=nsp_all[k]
        setar=np.concatenate([ad0,ad1])
        vals_set=data_impress["non_physical_value_"+str(ind)][setar[data_impress["DUAL_1"][setar]==2]] #Evita que I, J sobreponha J, I
        try:
            neta_p=max(neta_p,vals_set.max())
        except:
            neta_p=max(neta_p,vals_set)
        data_impress["non_physical_value_"+str(ind)][setar]=np.repeat(neta_p,len(setar))

    dual_volumes = M.multilevel_data['dual_structure_level_1']
    # dual_volumes = [dd['volumes'] for dd in dual_structure]

    dual_lines = [np.repeat(i,len(dual_volumes[i])) for i in range(len(dual_volumes))]
    # for dvv in range(len(dual_volumes)): #id_dual
    #     data_impress["perm_z"][dual_volumes[dvv]]=dual_lines[dvv]
    dvs=np.concatenate(dual_volumes)

    pvs=data_impress['GID_1'][dvs]
    dls=np.concatenate(dual_lines)
    data=np.repeat(1,len(pvs))
    dp=csc_matrix((data,(dls,pvs)),shape=(dls.max()+1, pvs.max()+1))
    dp[dp>1]=1
    cds=[]
    for k in range(len(i)):
        ddp_i=dp[:,i[k]]
        ddp_j=dp[:,j[k]]
        ddp=(ddp_i.sum(axis=1)>0) & (ddp_j.sum(axis=1)>0)
        duais_coup=np.arange(len(ddp))[np.array(ddp).T[0]]
        if len(duais_coup)>2:
            import pdb; pdb.set_trace()
        if len(duais_coup)==1:
            duais_coup=np.repeat(duais_coup[0],2)
        if len(duais_coup)==2:
            cds.append(duais_coup)

    cds=np.array(cds)
    if len(cds)>0:
        values=np.unique(np.concatenate(cds))
        mapd=np.arange(len(dual_volumes))
        mapd[values]=np.arange(len(values))

        lines=np.concatenate([mapd[cds[:,0]],mapd[cds[:,1]]])
        cols=np.concatenate([mapd[cds[:,1]],mapd[cds[:,0]]])

        data=np.ones(len(lines))
        graph=csc_matrix((data,(lines,cols)),shape=(len(values),len(values)))

        n_l,labels=csgraph.connected_components(graph,connection='strong')
        groups=[]
        for k in range(n_l):
            groups.append(values[labels==k])
        return groups
    else:
        return []

def get_dual_subdomains(groups):
    juntares=groups
    dv=[]
    for juntar in juntares:
        todos=np.arange(len(dual_volumes))
        keep_dual=np.setdiff1d(todos,juntar[1:])

        # dual_volumes = np.array(dual_volumes)
        dual_volumes2=dual_volumes[keep_dual]

        new_volume=np.unique(np.hstack(dual_volumes[juntar]))
        dv.append(new_volume)
    return(dv)

def plot_matrix(matrix,name,plot_values=False):
    import matplotlib.pyplot as plt
    matrix[matrix == 0] = np.nan
    colors = [(1, 0, 0), (0, 0, 0), (0, 0, 1)]  # R -> G -> B
    n_bin = 2
    cmap_name = 'my_list'
    cm = LinearSegmentedColormap.from_list(cmap_name, colors, N=n_bin)
    plt.matshow(matrix, cmap=cm, vmin=-1,vmax=1)
    # locs, labels = plt.xticks()
    # plt.xticks(grids)
    # plt.yticks(grids)
    # plt.grid()
    if plot_values:
        for (i, j), z in np.ndenumerate(matrix):
            plt.text(j, i, '{:0.1f}'.format(z), fontsize=20, ha='center', va='center', bbox=dict(boxstyle='round', facecolor='white', edgecolor='0.9'))
    plt.savefig(name+".png")

print("Preprocessing finescale mesh")
t0=time.time()
load = data_loaded['load_data']
convert = data_loaded['convert_english_to_SI']
n = data_loaded['n_test']
load_operators = data_loaded['load_operators']
get_correction_term = data_loaded['get_correction_term']
n_levels = int(data_loaded['n_levels'])
_debug = data_loaded['_debug']
t1=time.time()
M, elements_lv0, data_impress, wells = initial_mesh()
print("Time to preprocess finescale mesh: {}, {} seconds".format(time.time()-t0, time.time()-t1))
print("")
print("STARTING MULTILEVEL")
print("")
print("")
tml=time.time()
######################
print("Creating finescale system")
t0=time.time()
tpfa_solver = FineScaleTpfaPressureSolver(data_impress, elements_lv0, wells)
# tpfa_solver.get_transmissibility_matrix_without_boundary_conditions()
T, b = tpfa_solver.run()
print("Time to create finescale system: {} seconds".format(time.time()-t0))
# tpfa_solver.get_RHS_term()
# tpfa_solver.get_transmissibility_matrix()
print("Constructing operators")
t0=time.time()
dual_structure = M.multilevel_data['dual_structure_level_1']
dual_volumes = np.array([dd for dd in dual_structure])

multilevel_operators = MultilevelOperators(n_levels, data_impress, elements_lv0, M.multilevel_data, load=load_operators, get_correction_term=get_correction_term)
mlo=multilevel_operators
if load_operators:
    pass
else:
    # multilevel_operators.run(tpfa_solver['Tini'])
    multilevel_operators.run_paralel(tpfa_solver['Tini'],dual_volumes, 0, False)
print("Time to construct prolongation operator: {} seconds".format(time.time()-t0))
print("Adapting reduced boundary conditions")
t0=time.time()
neta_lim=9999999999999999991.0
OP_AMS=mlo['prolongation_level_1'].copy()
groups = get_coupled_dual_volumes(mlo,neta_lim, ind=0)

dv=get_dual_subdomains(groups)
if len(dv)>0:
    multilevel_operators.run_paralel(tpfa_solver['Tini'],dv,1,False)
    OP_AMS_groups=mlo['prolongation_level_1']
    lins_par=np.unique(np.concatenate(dv))
    OP_AMS[lins_par]=OP_AMS_groups[lins_par]
    mlo['prolongation_level_1']=OP_AMS
    multilevel_operators=mlo
######################### # #############################
old_groups=groups.copy()
if len(old_groups)==0:
    nref=0
else:
    nref=6

for ind in range(1,nref):

    groups2 = get_coupled_dual_volumes(mlo,neta_lim, ind=ind)
    # neta_lim/=2
    lgs=[np.repeat(i,len(old_groups[i])) for i in range(len(old_groups))]
    gs=np.concatenate(old_groups)
    lgs=np.concatenate(lgs)
    all_joined=np.zeros(len(gs))
    new_groups=[]
    for g2 in groups2:
        joins=np.zeros(len(gs))
        for g in g2:
            joins+= gs==g
            all_joined+= gs==g
        neighs=lgs[joins>0]
        if len(neighs)>0:
            aglomerated_dual=np.unique(np.concatenate([np.concatenate(np.array(old_groups)[neighs]),g2]))
        else:
            aglomerated_dual=g2
        new_groups.append(aglomerated_dual)
    inds_manteined=np.setdiff1d(lgs,np.unique(lgs[all_joined>0]))
    groups_manteined=np.array(old_groups)[inds_manteined]
    atualized_groups=groups_manteined.tolist()+new_groups

    print(ind,len(old_groups), len(atualized_groups),len(np.concatenate(atualized_groups)),"dsjjjjjja")
    dv=get_dual_subdomains(new_groups)
    if len(dv)>0:
        multilevel_operators.run_paralel(tpfa_solver['Tini'],dv,1,False)
        OP_AMS_groups=mlo['prolongation_level_1']
        lins_par=np.unique(np.concatenate(dv))
        OP_AMS[lins_par]=OP_AMS_groups[lins_par]
        mlo['prolongation_level_1']=OP_AMS
        multilevel_operators=mlo
    old_groups=atualized_groups.copy()
'''
# groups = get_coupled_dual_volumes(mlo,neta_lim, ind=5)
#
# gid_coarse_wells = np.unique(data_impress['GID_1'][finos])
# finos2 = np.concatenate([data_impress['GID_0'][data_impress['GID_1']==gidc] for gidc in gid_coarse_wells])
# # wells_prim=np.concatenate([M.volumes.all[data_impress["GID_1"]==w] for w in wells])
# finos=np.concatenate([finos,finos2])

# if len(groups)>0:
#     dv=np.concatenate(get_dual_subdomains(groups))
#     finos=np.concatenate([finos,dv])
'''
print("Time to adapt RBC: {} seconds".format(time.time()-t0))
finos=wells['all_wells']
# from packs.utils.utils_old import get_box
# dx=20
# dy=10
# dz=2
# #60 220
# bx=np.array([[dx*0,dy*53,dz*84],[dx*3,dy*63,dz*85]])
# vols=get_box(M.data['centroid_volumes'],bx)
# if len(vols)>0:
#     finos=np.concatenate([finos,vols])
# p0=M.volumes.all[(data_impress['GID_1']==0) |  (data_impress['GID_1']==5)]
# finos=np.concatenate([finos,p0])
# if len(lins_par)>0:
#     finos=np.concatenate([finos,lins_par])
t0=time.time()
data_impress.update_variables_to_mesh()
################################
ta=time.time()
adm_method = AdmNonNested(finos, n_levels, M, data_impress, elements_lv0)
print(time.time()-ta,"adm")
# adm_method = AdmNonNested(wells['all_wells'], n_levels, M, data_impress, elements_lv0)
t99=time.time()
adm_method.set_initial_mesh(mlo, T, b)
print(time.time()-t99,"INITIAL_ mesh")
t1=time.time()
T, b = tpfa_solver.run()
print(time.time()-t1,"tpfa")

gids_0 = data_impress['GID_0']
t3=time.time()
adm_method.set_adm_mesh_non_nested(gids_0[data_impress['LEVEL']==0])
print(time.time()-t3,"non mesh")
# adm_method.set_initial_mesh(mlo, T, b)
t4=time.time()
adm_method.organize_ops_adm(mlo['prolongation_level_1'],
                            mlo['restriction_level_1'],
                            1)
print(time.time()-t4, "organize")
# adm_method.plot_operator(adm_method[adm_method.adm_op_n+'1'], mlo['prolongation_level_1'], 0)

if n_levels > 2:
    adm_method.organize_ops_adm(mlo['prolongation_level_2'],
                                mlo['restriction_level_2'],
                                2)

print(time.time()-t0,"b1")
# len(np.arange(len(dual_volumes))[np.array(ddp.sum(axis=1)>2).T[0]])
# np.arange(len(dual_volumes))[np.array(dp.sum(axis=1)>3).T[0]]
t0=time.time()
OP_AMS=mlo['prolongation_level_1']
OR_AMS=mlo['restriction_level_1']
OP_ADM = adm_method['adm_prolongation_level_1']
OR_ADM = adm_method['adm_restriction_level_1']
plot_matrix((OR_AMS*tpfa_solver['Tini']*OP_AMS).toarray(), "finescale")
plot_matrix((OR_ADM*T*OP_ADM).toarray(), "adm")
# import pdb; pdb.set_trace()

Tc=OR_AMS*T*OP_AMS
bc=OR_AMS*b
from scipy.sparse import linalg
pc=linalg.spsolve(Tc,bc)

pms=OP_AMS*pc

Tcadm=OR_ADM*T*OP_ADM
bcadm = OR_ADM*b
pcadm=linalg.spsolve(Tcadm,bcadm)
padm=OP_ADM*pcadm
print("FINISHED MULTILEVEL WITH: {} SECONDS".format(time.time()-tml))

pf=linalg.spsolve(T,b)
eadm=np.linalg.norm(abs(padm-pf))/np.linalg.norm(pf)
eams=np.linalg.norm(abs(pms-pf))/np.linalg.norm(pf)
print("erro_adm: {}, erro_ams: {}".format(eadm,eams))
print(time.time()-t0,"t2")
# import pdb; pdb.set_trace()
# adm_method.organize_ops_adm_level_1( OP_AMS, OR_AMS, level, _pcorr=None)
#########################################################################
Tc=OR_AMS*tpfa_solver['Tini']*OP_AMS
t0=time.time()
Tc2=Tc.copy()
Tc2.setdiag(0)
DTc=np.array(Tc[range(Tc.shape[0]),range(Tc.shape[0])])[0]
MTc=Tc2.min(axis=1).toarray().T[0]
netasams=abs(MTc/DTc)

Tcadm2=Tcadm.copy()
Tcadm2.setdiag(0)
DTcadm=np.array(Tcadm[range(Tcadm.shape[0]),range(Tcadm.shape[0])])[0]
MTcadm=Tcadm2.min(axis=1).toarray().T[0]
netasadm=abs(MTcadm/DTcadm)
print(time.time()-t0,"t3")
print("netamax: adm: {}, ams: {}".format(netasadm.max(), netasams.max()))
# v_edges=M.volumes.all[data_impress["DUAL_1"]>=2]
# f_edges=np.intersect1d(M.faces.internal,np.unique(np.concatenate(M.volumes.bridge_adjacencies(v_edges, 2, 2))))
# adjs_e=M.faces.bridge_adjacencies(f_edges, 2, 3)
# adjs_e0=adjs_e[:,0]
# adjs_e1=adjs_e[:,1]
# pe0=padm[adjs_e0]
# pe1=padm[adjs_e1]
# dpe=abs(pe0-pe1)
#
# lines=np.concatenate([adjs_e0,adjs_e1])
# cols=np.concatenate([adjs_e1,adjs_e0])
# data=np.concatenate([dpe,dpe])
# from scipy.sparse import csc_matrix
# sums=csc_matrix((data,(lines,cols)),shape=(len(M.volumes.all),len(M.volumes.all)))
# sums=sums[:,M.volumes.all[data_impress["DUAL_1"]<2]]
# ss=np.array(sums.sum(axis=1)).T[0]
# # np.where(ss>100)
# # ss[data_impress["DUAL_1"]<2]=0
# data_impress["velocity_projection"]=ss
#
# superam_tol_for_v=data_impress["GID_1"][M.volumes.all[ss>1]]
# vsup=[]
# for v in superam_tol_for_v:
#     vsup.append(M.volumes.all[data_impress["GID_1"]==v])

perms=np.load("flying/permeability.npy")
perms_xx=perms[:,0]
data_impress["perm_x"]=perms_xx
data_impress['pcorr'][data_impress['LEVEL']==0] = data_impress['pms'][data_impress['LEVEL']==0]

faces=M.faces.internal
adjs=M.faces.bridge_adjacencies(faces,2,3)
centroids=M.volumes.center[:]
ca=centroids[adjs]
dc=abs(ca[:,0]-ca[:,1]).max(axis=1)

t_f=data_impress['transmissibility'][faces]
a0=adjs[:,0]
a1=adjs[:,1]

vadm=t_f*((padm[a0]-padm[a1])/dc)
vams=t_f*((pms[a0]-pms[a1])/dc)
vf=t_f*((pf[a0]-pf[a1])/dc)
l2_v_adm=np.linalg.norm(vadm-vf)/np.linalg.norm(vf)
l2_v_ams=np.linalg.norm(vams-vf)/np.linalg.norm(vf)
linf_v_adm=(abs(vadm-vf)/abs(vf)).max()
linf_v_ams=(abs(vams-vf)/abs(vf)).max()

padm=padm/padm[wells['all_wells']].max()
poco_min_p=wells['all_wells'][padm[wells['all_wells']]==padm[wells['all_wells']].min()]
padm[poco_min_p]=0
pf=pf/pf[wells['all_wells']].max()
pf[poco_min_p]=0

data_impress['pressure'] = padm
data_impress['tpfa_pressure'] = pf
data_impress['erro'] = np.absolute((padm - pf))[pf>0]/pf[pf>0]
# data_impress['erro_pcorr_pdm'] = np.absolute(data_impress['pcorr'] - data_impress['pms'])

get_coupled_dual_volumes(mlo, neta_lim=neta_lim, ind=999)
data_impress.update_variables_to_mesh()
M.core.print(file='results/test_'+ str(0), extension='.vtk', config_input='input_cards/print_settings0.yml')

with open('input_cards/saves_test_cases.yml', 'r') as f:
    data_loaded = yaml.safe_load(f)
folder_=data_loaded['directory']
file_=folder=data_loaded['file']
alpha=np.array([1.00,2.0,3.0,4.0,4.5,5.0, 10.0, 20.0, 50.0, 200.0, 1000.0, 10000.0])
neta= np.array([0.00,0.0,0.0,0.0,0.022,0.0416, 0.136, 0.190, 0.225, 0.2437, 0.249, 0.250])

kb=np.array([1e1,1e2, 1e3, 1e4, 1e5, 1e6])
netab=np.array([0.08,0.086,0.088, 0.088, 0.088, 0.088]) #x de 0 a 1 e y de 1 a 2
netac=np.array([0.15, 0.95, 1.18, 1.20, 1.21, 1.21]) # x de o a 3 y de 1 a 2
kd=np.array([1e1,1e2, 1e3, 1e4, 1e5, 1e6,1e12])
netad=np.array([0.04, 8.67, 95.23, 960.82, 9616.68, 96174,14782938413]) #x de 0 a 3 y de 0 a 1
netae=np.array([0.83, 9.23, 93.22, 933,9355, 93359]) #x de 0 a 1 t de 0 a 1
netaf=np.array([0.05, 0.78, 0.97, 1.0, 1.0, 1.0]) #x de 0 a 6 t de 1 a 2

#cruz_global_tests

kcruz=perms[perms>0].min()
neta_adm = netasadm.max()
neta_ams = netasams.max()
ev_l2_adm =l2_v_adm
ev_l2_ams =l2_v_ams
ev_linf_adm =linf_v_adm
ev_linf_ams =linf_v_ams


try:
    cruz_r=np.load("cruz_results.npy")
    cruz_r=np.concatenate(cruz_r,np.array([[kcruz],[neta_adm],[neta_ams],[ev_l2_adm],[ev_l2_ams],[ev_linf_adm],[ev_linf_ams]]))
except:
    cruz_r=np.array([[kcruz],[neta_adm],[neta_ams],[ev_l2_adm],[ev_l2_ams],[ev_linf_adm],[ev_linf_ams]])
np.save("cruz_results.npy",cruz_r)
kcruz=[]
netacruz=[]
normal2_cruz=[]


# import matplotlib.pyplot as plt
# plt.close("all")
# # plt.plot(alpha,neta)
# plt.plot(kb,netab)
# plt.plot(kb,netac)
# plt.plot(kd[:-1],netad[:-1])
# plt.plot(kb,netae)
# plt.plot(kb,netaf)
# plt.xscale("log")
# plt.yscale("log")
# plt.legend()
# plt.grid(True)
# plt.ylabel("Neta")
# plt.xlabel("Anisotropy (Kyy/Kxx)")
# plt.savefig("log_alpha_versus_neta.png")
M.core.print(file=folder_+'/'+file_, extension='.vtk', config_input='input_cards/print_settings0.yml')
# import pdb; pdb.set_trace()
