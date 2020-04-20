from pymoab import rng, types
import scipy
import numpy as np
import multiprocessing as mp
from scipy.sparse import csc_matrix,csr_matrix, linalg, vstack, find
import time
from packs.multiscale.operators.prolongation.AMS.Paralell.partitionating_parameters import calibrate_partitioning_parameters
import yaml
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

class DualDomain:
    def __init__(self, data_impress, elements_lv0, volumes, id_dual, local_couple=0, couple_bound=True):
        self.id_dual=id_dual
        self.local_couple=local_couple
        self.couple_bound=couple_bound
        self.adjs, self.ks, self.ids_globais_vols, self.ns, self.map_l =  self.get_local_informations(data_impress, elements_lv0, volumes, local_couple=local_couple, couple_bound=couple_bound)
        self.coarse_ids = data_impress['GID_1'][self.vertices]
        self.all_coarse_ids = data_impress['GID_1'][volumes]
        # import pdb; pdb.set_trace()
        self.A_b_t=[]

    def get_local_informations(self, data_impress, elements_lv0, volumes, local_couple=0, couple_bound=True):
        # viz=M.mtu.get_bridge_adjacencies(volumes,2,3)
        viz=np.unique(np.concatenate(elements_lv0['volumes_face_volumes'][volumes]))
        nv=len(volumes)
        # M.mb.tag_set_data(M.local_id_dual_tag,viz, np.repeat(nv+5,len(viz)))
        # faces_entities=M.mtu.get_bridge_adjacencies(volumes,2,2)
        faces_entities = np.unique(np.concatenate(elements_lv0['volumes_face_faces'][volumes]))
        int_facs=np.setdiff1d(faces_entities, elements_lv0['boundary_faces'])

        so_viz=np.setdiff1d(viz,volumes)
        if len(so_viz) > 0:
            so_viz_faces=np.unique(np.concatenate(elements_lv0['volumes_face_faces'][so_viz]))
            int_facs=np.setdiff1d(int_facs,so_viz_faces)

        dual_id_volumes = data_impress['DUAL_1'][volumes]
        if local_couple>0:
            # dual_flags=M.mb.tag_get_data(M.D1_tag, np.array(volumes),flat=True)
            dual_flags=np.repeat(-1,len(elements_lv0["volumes"]))
            dual_flags[volumes]=dual_id_volumes
            if couple_bound:
                reduce_flag=volumes
                volumes_red=volumes
                dual_flags_red=dual_flags[reduce_flag]
                dual_flags_red[dual_flags_red==2]=1
                if local_couple==2:
                    dual_flags_red[dual_flags_red==1]=0

            else:
                try:
                    reduce_flag = np.setdiff1d(volumes, np.concatenate(elements_lv0['volumes_face_volumes'][so_viz]))
                except:
                    reduce_flag = volumes
                volumes_red = reduce_flag

                dual_flags_red=dual_flags[reduce_flag]
                dual_flags_red[dual_flags_red==2]-=1
                if local_couple==2:
                    dual_flags_red[dual_flags_red==1]=0


            # M.mb.tag_set_data(M.D1_tag,volumes_red,dual_flags_red)
            data_impress['DUAL_1'][volumes_red] = dual_flags_red
            dual_id_volumes = data_impress['DUAL_1'][volumes]

        vertices = volumes[dual_id_volumes==3]
        edges = volumes[dual_id_volumes==2]
        faces = volumes[dual_id_volumes==1]
        internals = volumes[dual_id_volumes==0]

        nv=len(vertices)
        ne=len(edges)
        nf=len(faces)
        ni=len(internals)
        ns=[nv,ne,nf,ni]

        self.vertices = vertices

        adjs = elements_lv0['faces_face_volumes'][int_facs]
        adjs = np.concatenate(adjs).reshape((adjs.shape[0], 2))

        map_l=np.zeros(adjs.max()+1)
        map_l[internals]=np.arange(ni)
        map_l[faces]=np.arange(ni,ni+nf)
        map_l[edges]=np.arange(ni+nf,ni+nf+ne)
        map_l[vertices]=np.arange(ni+nf+ne, ni+nf+ne+nv)

        adjs_l0=map_l[adjs[:,0]]
        adjs_l1=map_l[adjs[:,1]]

        adjs=np.array([adjs_l0, adjs_l1]).T
        # ks=M.mb.tag_get_data(M.k_eq_tag,np.uint64(int_facs)[vv],flat=True)
        ks=data_impress['transmissibility'][int_facs]
        # ids_globais_vols=M.mb.tag_get_data(M.ID_reordenado_tag,np.concatenate([np.uint64(internals),np.uint64(faces), np.uint64(edges),vertices]),flat=True)
        ids_globais_vols=np.concatenate([np.uint64(internals),np.uint64(faces), np.uint64(edges),vertices])

        return adjs, ks, ids_globais_vols, ns, map_l[volumes]


class OP_local:
    def __init__(self, sub_d, return_netas, neta_lim):
        if return_netas:
            self.lcd_OP_local, self.netas = self.get_OP(sub_d, return_netas, neta_lim) #ordem IJN
        else:
            self.lcd_OP_local = self.get_OP(sub_d)

    def get_submatrix(self,id0, id1, ks, slice):
        id0, id1, ks= np.concatenate([id0,id1]), np.concatenate([id1,id0]), np.concatenate([ks, ks])
        (xi, xs, yi, ys)=slice
        inds =(id0>=xi) & (id0<xs) & (id1>=yi) & (id1<ys)

        l1=id0[inds]-xi
        c1=id1[inds]-yi
        d1=ks[inds]
        if xi==yi:
            inds_sup0=((id0>=xi) & (id0<xs) & (id1>=ys))
            ls0=id0[inds_sup0]-xi
            cs0=ls0
            ds0=-ks[inds_sup0]

            l=np.concatenate([l1,l1, ls0])
            c=np.concatenate([c1,l1, cs0])
            d=np.concatenate([d1,-d1, ds0])
        else:
            l=l1
            c=c1
            d=d1
        submatrix=csc_matrix((d,(l,c)),shape=(xs-xi,ys-yi))
        return(submatrix)

    def get_OP(self, sub_d, return_netas = False, neta_lim=10):
        adjs, ks, ids_globais_vols, ns = sub_d.adjs, sub_d.ks, sub_d.ids_globais_vols, sub_d.ns
        nv=ns[0]
        ne=ns[1]
        nf=ns[2]
        ni=ns[3]

        adjs0=adjs[:,0]
        adjs1=adjs[:,1]

        II=self.get_submatrix(adjs0, adjs1, ks, (0, ni, 0, ni))
        IF=self.get_submatrix(adjs0, adjs1, ks, (0, ni, ni, ni+nf))

        if sub_d.local_couple>0:
            IE=self.get_submatrix(adjs0, adjs1, ks, (0, ni, ni+nf, ni+nf+ne))
            IV=self.get_submatrix(adjs0, adjs1, ks, (0, ni, ni+nf+ne, ni+nf+ne+nv))

        FF=self.get_submatrix(adjs0, adjs1, ks, (ni, ni+nf, ni, ni+nf))
        FE=self.get_submatrix(adjs0, adjs1, ks, (ni,ni+nf, ni+nf,ni+nf+ne))

        if sub_d.local_couple>0:
            FV=self.get_submatrix(adjs0, adjs1, ks, (ni, ni+nf, ni+nf+ne, ni+nf+ne+nv))

        EE=self.get_submatrix(adjs0, adjs1, ks, (ni+nf, ni+nf+ne, ni+nf, ni+nf+ne))
        EV=self.get_submatrix(adjs0, adjs1, ks, (ni+nf, ni+nf+ne, ni+nf+ne, ni+nf+ne+nv))

        Pv=scipy.sparse.identity(nv)
        t0=time.time()
        Pe=-linalg.spsolve(EE,EV*Pv)
        sub_d.A_b_t.append([EE.shape[0], nv,time.time()-t0])
        if sub_d.local_couple==0:
            t0=time.time()
            Pf=-linalg.spsolve(FF,FE*Pe)
            sub_d.A_b_t.append([FF.shape[0], nv,time.time()-t0])
            t0=time.time()
            Pi=-linalg.spsolve(II,IF*Pf)
            sub_d.A_b_t.append([II.shape[0], nv,time.time()-t0])
        else:
            t0=time.time()
            Pf=-linalg.spsolve(FF,FE*Pe+FV)
            sub_d.A_b_t.append([FF.shape[0], nv,time.time()-t0])
            t0=time.time()
            Pi=-linalg.spsolve(II,IF*Pf+IE*Pe+IV)
            sub_d.A_b_t.append([II.shape[0], nv,time.time()-t0])

        OP=vstack([Pi,Pf,Pe,Pv])
        lcd=scipy.sparse.find(OP)
        lines=ids_globais_vols[np.array(lcd[0])].astype(int)
        cols = sub_d.coarse_ids[lcd[1]].astype(int)
        data=np.array(lcd[2])
        if return_netas:
            IJN = self.get_netas(sub_d, OP, neta_lim)
            return (lines, cols, data), IJN
        else:
            return (lines, cols, data)

    def get_netas(self, sub_d, OP, neta_lim=0):
        adjs, ks, ids_globais_vols, ns = sub_d.adjs, sub_d.ks, sub_d.ids_globais_vols, sub_d.ns
        nv, ne, nf, ni = ns
        adjs0=adjs[:,0]
        adjs1=adjs[:,1]
        TL=self.get_submatrix(adjs0, adjs1, ks, (0, ni+nf+ne+nv, 0, ni+nf+ne+nv))
        cid=sub_d.all_coarse_ids
        sub_d.coarse_ids
        map_p=np.arange(sub_d.coarse_ids.max()+1)
        map_p[sub_d.coarse_ids]=np.arange(len(sub_d.coarse_ids))
        lcid=map_p[cid]
        lines=lcid
        cols=sub_d.map_l
        data=np.ones(len(lines))
        OR=csc_matrix((data,(lines,cols)),shape=(nv, ni+nf+ne+nv))

        MM=OR*TL*OP
        ii=np.array(MM[range(nv),range(nv)])[0]
        inv_ii=1/ii
        lc=np.arange(nv)
        d_inv_ii=csc_matrix((inv_ii, (lc,lc)),shape=(nv,nv))
        MM2=MM.copy()
        MM2.setdiag(0)
        netas=d_inv_ii*MM2
        with open('input_cards/saves_test_cases.yml', 'r') as f:
            data_loaded = yaml.safe_load(f)
        folder_=data_loaded['directory']
        file_=folder=data_loaded['file']
        np.save(folder_+'/'+file_+str(sub_d.id_dual)+'.npy',MM.toarray())
        np.save(folder_+'/'+file_+str(sub_d.id_dual)+'TL'+'.npy',TL.toarray())
        WM=TL.toarray()
        d0=np.zeros(nf)
        d1=WM[nf:nf+ne,0:nf].sum(axis=1)
        d2=WM[nf+ne:nf+ne+nv,:nf+ne].sum(axis=1)
        dd=np.concatenate([d0, d1, d2])+1
        WM[range(len(dd)),range(len(dd))]+=dd

        WM[nf:,0:nf]=0
        WM[nf+ne:,0:nf+ne]=0
        grids=np.array([0, ni+nf, ni+nf+ne, ni+nf+ne+nv])-0.5
        lims=np.array([min(WM.min(), MM.min(),TL.min()),max(WM.max(), MM.max(),TL.max())])

        self.plot_matrix(TL.toarray(),"W",grids, lims)
        self.plot_matrix(WM,"WM",grids, lims)
        grids=np.arange(0,nv)-0.5

        self.plot_matrix(MM.toarray(),"Coarse",grids,lims, plot_values=True)
        ns=netas.copy()
        ns[netas<0]=0
        self.plot_matrix(ns.toarray(),"Netas",grids,lims, plot_values=True)

        if netas.max()>neta_lim:
            fn=find(netas>neta_lim)
            i=sub_d.coarse_ids[fn[0]]
            j=sub_d.coarse_ids[fn[1]]
            n=np.array(netas[netas>neta_lim])[0]
            return np.concatenate([i, j, n,np.repeat(sub_d.id_dual,len(i))])

        else:
            return []
    def plot_matrix(self,matrix,name,grids,lims,plot_values=False):
        import matplotlib.pyplot as plt
        matrix[matrix == 0] = np.nan
        colors = [(1, 0, 0), (0, 0, 0), (0, 0, 1)]  # R -> G -> B
        n_bin = 2
        cmap_name = 'my_list'
        cm = LinearSegmentedColormap.from_list(cmap_name, colors, N=n_bin)
        plt.matshow(matrix, cmap=cm, vmin=-1,vmax=1)
        locs, labels = plt.xticks()
        plt.xticks(grids)
        plt.yticks(grids)
        plt.grid()
        if plot_values:
            for (i, j), z in np.ndenumerate(matrix):
                if z<np.inf:
                    plt.text(j, i, '{:0.1f}'.format(z), fontsize=20, ha='center', va='center', bbox=dict(boxstyle='round', facecolor='white', edgecolor='0.9'))
        plt.savefig(name+".png")


class Partitioner:
    def __init__(self,all_subds, nworker, regression_degree):
        if len(all_subds)>0:
            estimated_time_by_subd = self.get_estimated_time_by_subd(all_subds,regression_degree)
            partitioned_subds = self.balance_processes(all_subds, estimated_time_by_subd, nworker=nworker)
            self.partitioned_subds = partitioned_subds
        else:
            self.partitioned_subds=np.array([[],[],[]])
        # A_b_t=np.zeros((1,3))
        # for subd in all_subds:
        #     A_b_t=np.vstack([A_b_t,np.array(subd.A_b_t)])
        # A_b_t=A_b_t[1:,:]
        # try:
        #     Abt=np.load("flying/A_b_t.npy")
        #     A_b_t=np.vstack([A_b_t,Abt])
        #     np.save("flying/A_b_t.npy",A_b_t)
        # except:
        #     np.save("flying/A_b_t.npy",A_b_t)


    def get_estimated_time_by_subd(self, all_subds, regression_degree = 2):
        n_A = [np.array(subd.ns) for subd in all_subds]

        n_b = [subd.ns[0] for subd in all_subds]
        try:
            n_A=np.array(n_A)[:,1:]
        except:
            import pdb; pdb.set_trace()
        n_b=np.array(n_b)
        if regression_degree==1:
            print("linear")
            cx, cy, intercept = np.load("flying/partitioning_coeffitients_cx_cy_intercept.npy")
            cx2, cxy, cy2 = 0, 0, 0
        else:
            print("quadrático")
            try:
                cx, cy, cx2, cxy, cy2, intercept= np.load("flying/partitioning_coeffitients_bx_cy_dx2_exy_fy2_intercept.npy")
            except:
                calibrate_partitioning_parameters()
                cx, cy, cx2, cxy, cy2, intercept= np.load("flying/partitioning_coeffitients_bx_cy_dx2_exy_fy2_intercept.npy")

        x=n_A
        y=np.array([n_b]).T
        estimated_time_by_subd=(cx*x+cy*y+cx2*x*x+cxy*x*y+cy2*y*y+intercept).sum(axis=1)
        return estimated_time_by_subd

    def balance_processes(self, all_subds, estimated_time_by_subd, nworker=1):
        if nworker>len(all_subds):
            print("more workers than subdomains, working with {} processes".format(len(all_subds)))
            nworker=len(all_subds)

        parts = np.zeros((nworker,len(all_subds)))
        u_vals=-np.sort(np.unique(-estimated_time_by_subd))
        for u in u_vals:
            posics=np.arange(len(estimated_time_by_subd))[estimated_time_by_subd==u]
            for p in posics:
                worker_id=np.arange(nworker)[parts.sum(axis=1)==parts.sum(axis=1).min()][0]
                parts[worker_id,p]=estimated_time_by_subd[p]
        if (parts!=0).sum(axis=0).min()!=1 or (parts>0).sum(axis=0).min()!=1:
            print("verificar particionamento")
            import pdb; pdb.set_trace()
        print(parts.sum(axis=1), (parts>0).sum(axis=1),len(all_subds),"aqui")

        partitioned_subds=[]
        for i in range(nworker):
            partitioned_subds.append(np.array(all_subds)[parts[i]>0])

        return partitioned_subds

class OP_AMS:
    def __init__(self, data_impress, elements_lv0, all_conjs_duais, local_couple=0, couple_bound=True):
        t0=time.time()

        print("Time to calibrate partitioning parameters: {} segundos".format(time.time()-t0))
        t0=time.time()
        all_subds = [DualDomain(data_impress, elements_lv0, all_conjs_duais[i], i, local_couple=local_couple, \
        couple_bound = couple_bound) for i in range(len(all_conjs_duais))]
        print("Time to partitionate subdomains: {} segundos".format(time.time()-t0))

        Nvols=len(elements_lv0['volumes'])
        Nverts = (data_impress['DUAL_1']==3).sum()
        regression_degree=2
        nworker=3

        # partitioned_subds=Partitioner(all_subds, nworker, regression_degree).partitioned_subds
        # print("started OP")
        # t0=time.time()
        # (lines, cols, data), IJN = self.get_OP_paralell(partitioned_subds)
        # IJN=np.hstack([ijn.reshape(4,round(len(ijn)/4)) for ijn in IJN]).T
        # IJ=IJN[:,0:2].astype(int)
        # N=IJN[:,2]
        # ID=IJN[:,3].astype(int)

        # self.OP=csc_matrix((data,(lines,cols)),shape=(Nvols,Nverts))
        # print("finished OP after {} seconds",time.time()-t0 )

        # #########To test bugs on serial, use this###############################

        (lines, cols, data), IJN = self.get_OP(all_subds, paralell=False)

        self.OP=csc_matrix((data,(lines,cols)),shape=(Nvols,Nverts))

        # ######################################

    def get_OP(self,partitioned_subd, paralell=True):
        if paralell:
            print("process {} started".format(partitioned_subd[-1].id))
        t0=time.time()
        # Processes imputs
        ################################
        lcd=np.zeros((3,1))
        IJN=[]
        for dual_d in partitioned_subd:
            OP = OP_local(dual_d, return_netas=True, neta_lim=0)
            lcd_OP_local, netas = OP.lcd_OP_local, OP.netas
            lcd=np.hstack([lcd,lcd_OP_local])
            if len(netas)>0:
                IJN.append(netas)

        ###################################

        # Send results to master process
        ###################################################
        if paralell:
            print("process {} finished after {}".format(partitioned_subd[-1].id, time.time()-t0))
            master=dual_d.master
            master.send([lcd, IJN])
            #############################################
        else:
            return lcd, IJN

    def get_OP_paralell(self, partitioned_subds):
        nworker = len(partitioned_subds)
        print("calculating prolongation operator with {} processes".format(nworker))

        # Setup communication structure
        #########################################
        master2worker = [mp.Pipe() for p in range(nworker)]
        m2w, w2m = list(zip(*master2worker))
        for i in range(len(partitioned_subds)):
            partitioned_subds[i][-1].master = w2m[i]
            partitioned_subds[i][-1].id = i
        ########################################

        # Creates & start processes
        #########################################
        procs = [mp.Process(target=self.get_OP, args=[s]) for s in partitioned_subds]
        for p in procs:
            p.start()
        #########################################

        # Get processed output & kill subprocesses
        #################################
        l=[]
        c=[]
        d=[]
        IJN=[]
        for m in m2w:
            ms=m.recv()
            msg=ms[0]
            IJN.append(ms[1])
            l.append(msg[0])
            c.append(msg[1])
            d.append(msg[2])
        IJN=np.concatenate(IJN)
        l=np.concatenate(l)
        c=np.concatenate(c)
        d=np.concatenate(d)
        for p in procs:
            p.join()
        ###############################################
        lines=l.astype(int)
        cols=c.astype(int)
        data=d
        return (lines, cols, data), IJN
