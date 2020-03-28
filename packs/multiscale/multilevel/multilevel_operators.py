from ...data_class.data_manager import DataManager
from ..operators.prolongation.AMS.ams_tpfa import AMSTpfa
from ..operators.prolongation.AMS.ams_mpfa import AMSMpfa
import numpy as np
import scipy.sparse as sp
import os
from ...multiscale.operators.prolongation.AMS import paralel_ams
from ...multiscale.ms_utils.matrices_for_correction import MatricesForCorrection as mfc

from ..operators.prolongation.AMS.coupled_ams import OP_AMS

def get_gids_primalids_dualids(gids, primal_ids, dual_ids):

    gids2 = np.unique(gids)
    # ids = np.arange(len(gids))
    primal_ids2 = []
    dual_ids2 = []
    for i in gids2:
        # test = ids[gids==i]
        test = gids==i
        primal_id = np.unique(primal_ids[test])
        dual_id = np.unique(dual_ids[test])
        if len(primal_id) > 1 or len(dual_id) > 1:
            raise ValueError('erro get_gids_primalids_dualids')
        primal_ids2.append(primal_id[0])
        dual_ids2.append(dual_id[0])

    primal_ids2 = np.array(primal_ids2)
    dual_id = np.array(dual_ids2)

    return gids2, primal_ids2, dual_ids2

def manter_vizinhos_de_face(T, ids, neigh_ids):
    T2 = T.copy()
    nl = T2.shape[0]
    map_neig = dict(zip(ids, neigh_ids))

    for i in range(nl):
        neigs = set(map_neig[i])
        data = sp.find(T[i])
        cols = data[1]
        vals = data[2]
        # id_line = cols==i
        viz_rem = []

        for viz, val in zip(cols, vals):
            if set([viz]) & neigs or viz == i:
                pass
            else:
                viz_rem.append(viz)
                T2[i, i] += val
        viz_rem = np.array(viz_rem)
        T2[np.repeat(i, len(viz_rem)), viz_rem] = np.zeros(len(viz_rem))

    data_t2 = sp.find(T2)
    T2 = sp.csc_matrix((data_t2[2], (data_t2[0], data_t2[1])), shape=(nl, nl))

    return T2

class MultilevelOperators(DataManager):
    def __init__(self,
        n_levels,
        data_impress,
        elements_lv0,
        ml_data,
        data_name='MultilevelOperators.npz',
        load=False,
        get_correction_term=False,
    ):

        super().__init__(data_name=data_name, load=load)
        self.load = load
        self.ml_data = ml_data

        self.n_levels = n_levels
        self.data_impress = data_impress
        self.get_correction_term = get_correction_term
        self.elements_lv0 = elements_lv0

        self.restriction = 'restriction_level_'
        self.prolongation = 'prolongation_level_'
        self.infos_level = 'infos_level_'
        self.gid_n = 'gid'
        self.primal_id_n = 'primal_id'
        self.dual_id_n = 'dual_id'
        self.pcorr_n = 'pcorr_level_'
        self.operators = dict()

        if load == False:
            self.get_initial_infos()

        self.get_operators()

        if load == True:
            for n in range(n_levels):
                prol_name = self.prolongation + str(n+1)
                rest_name = self.restriction + str(n+1)
                OP = sp.load_npz(os.path.join('flying', prol_name + '.npz'))
                OR = sp.load_npz(os.path.join('flying', rest_name + '.npz'))
                self._data[prol_name] = OP
                self._data[rest_name] = OR
        else:
            self.export_to_npz()

    def get_initial_infos(self):
        t1 = np.dtype(int)
        dt = [(self.gid_n, t1),
              (self.primal_id_n, t1),
              (self.dual_id_n, t1)]

        for n in range(1, self.n_levels):

            gids = self.data_impress['GID_' + str(n-1)]
            primal_ids = self.data_impress['GID_' + str(n)]
            dual_ids = self.data_impress['DUAL_' + str(n)]
            if n > 1:
                gids, primal_ids, dual_ids = get_gids_primalids_dualids(gids, primal_ids, dual_ids)
            tam = len(gids)
            tam2 = len(np.unique(primal_ids))
            structured_array = np.zeros(tam, dtype=dt)
            structured_array[self.gid_n] = gids
            structured_array[self.primal_id_n] = primal_ids
            structured_array[self.dual_id_n] = dual_ids
            self._data[self.infos_level + str(n)] = structured_array
            data_r = np.ones(tam)
            lines = primal_ids
            cols = gids
            OR = sp.csc_matrix((data_r,(lines,cols)), shape=(tam2, tam))
            self._data[self.restriction + str(n)] = OR

    def get_operators(self, load=False):

        get_correction_term = self.get_correction_term

        for n in range(1, self.n_levels):
            level = n
            infos = self._data[self.infos_level + str(level)]
            gid = infos[self.gid_n]
            primal_id = infos[self.primal_id_n]
            dual_id = infos[self.dual_id_n]
            interns = gid[dual_id==0]
            faces = gid[dual_id==1]
            edges = gid[dual_id==2]
            vertices = gid[dual_id==3]
            if level == 1:
                operator = AMSTpfa
                tpfalizar = False
            else:
                # operator = AMSMpfa
                operator = AMSTpfa
                # tpfalizar = True
                tpfalizar = False
            self.operators[str(level)] = operator(interns,
                                                 faces,
                                                 edges,
                                                 vertices,
                                                 gid,
                                                 primal_id,
                                                 load=load,
                                                 tpfalizar=tpfalizar,
                                                 get_correction_term=get_correction_term)

    def run(self, T: 'fine transmissibility without boundary conditions',
        total_source_term: 'total fine source term'=None,
        q_grav: 'fine gravity source term'=None):
        T_ant = T.copy()
        for n in range(1, self.n_levels):
            level = n
            if self.get_correction_term:
                if level > 1:
                    total_source_term = OR*total_source_term
                    q_grav = OR*q_grav
                volumes_without_grav = self.ml_data['volumes_without_grav_level_'+str(n-1)]
                B_matrix = mfc.get_B_matrix(total_source_term, q_grav)
                Eps_matrix = mfc.get_Eps_matrix(np.arange(len(total_source_term)), volumes_without_grav)
            else:
                B_matrix = None
                Eps_matrix = None
                total_source_term = None

            OP, pcorr = self.operators[str(level)].run(T_ant, total_source_term=total_source_term, B_matrix=B_matrix, Eps_matrix=Eps_matrix)
            # import pdb; pdb.set_trace()
            self._data[self.prolongation + str(level)] = OP
            self._data[self.pcorr_n + str(level-1)] = pcorr
            OR = self._data[self.restriction + str(level)]

            sp.save_npz(os.path.join('flying', self.prolongation + str(level) + '.npz'), OP)
            sp.save_npz(os.path.join('flying', self.restriction + str(level) + '.npz'), OR)

            if level == self.n_levels-1:
                continue

            T_ant = OR*T_ant*OP
            cids_neigh = self.ml_data['coarse_id_neig_face_level_'+str(level)]
            cids_level = self.ml_data['coarse_primal_id_level_'+str(level)]
            T_ant = manter_vizinhos_de_face(T_ant, cids_level, cids_neigh)

        self.export_to_npz()

    def run_paralel_dep0(self, T: 'fine transmissibility without boundary conditions'):
        T_ant = T.copy()  #T(l-1)

        for n in range(1, self.n_levels):
            level = n
            master = paralel_ams.MasterOP(T_ant, self.ml_data['dual_structure_level_'+str(level)], level)
            OP = master.run()
            del master
            self._data[self.prolongation + str(level)] = OP
            OR = self._data[self.restriction + str(level)]

            sp.save_npz(os.path.join('flying', self.prolongation + str(level) + '.npz'), OP)
            sp.save_npz(os.path.join('flying', self.restriction + str(level) + '.npz'), OR)

            if level == self.n_levels-1:
                continue
            T_ant = OR*T_ant*OP
            cids_neigh = self.ml_data['coarse_id_neig_face_level_'+str(level)]
            cids_level = self.ml_data['coarse_primal_id_level_'+str(level)]
            T_ant = manter_vizinhos_de_face(T_ant, cids_level, cids_neigh)

        self.export_to_npz()

    def run_paralel(self, T):

        T_ant = T.copy()  #T(l-1)

        for n in range(1, self.n_levels):
            level = n

            OP = self.get_OP_paralel(level)
            self._data[self.prolongation + str(level)] = OP
            OR = self._data[self.restriction + str(level)]

            sp.save_npz(os.path.join('flying', self.prolongation + str(level) + '.npz'), OP)
            sp.save_npz(os.path.join('flying', self.restriction + str(level) + '.npz'), OR)

            if level == self.n_levels-1:
                continue
            T_ant = OR*T_ant*OP
            cids_neigh = self.ml_data['coarse_id_neig_face_level_'+str(level)]
            cids_level = self.ml_data['coarse_primal_id_level_'+str(level)]
            T_ant = manter_vizinhos_de_face(T_ant, cids_level, cids_neigh)

    def get_OP_paralel(self, level):

        dual_structure = self.ml_data['dual_structure_level_'+str(level)]
        dual_volumes = [dd['volumes'] for dd in dual_structure]
        rr = [np.unique(np.concatenate(dual_volumes[0:2]))]
        dual_volumes = rr + dual_volumes[2:]
        local_couple = 2
        couple_bound = False
        for dd in dual_volumes:
            try:
                OP += OP_AMS(self.data_impress, self.elements_lv0, dd, local_couple=local_couple, couple_bound=couple_bound).OP
            except:
                OP = OP_AMS(self.data_impress, self.elements_lv0, dd, local_couple=local_couple, couple_bound=couple_bound).OP
        diag=np.array(1/OP.sum(axis=1))[:,0]
        l=range(len(diag))
        c=l
        mult=sp.csc_matrix((diag,(l,c)),shape=(len(diag), len(diag)))
        OP=mult*OP
        return OP
