# from packs.solvers.solvers_scipy.solver_sp import SolverSp
# from packs.running.run_simulation import RunSimulation
# # from packs.direct_solution.monophasic.monophasic1 import Monophasic
# from packs.direct_solution.biphasic.biphasic1 import Biphasic
# from packs.preprocess.preprocess1 import Preprocess1
import pdb
#
# rodar = RunSimulation(state=5)
# M = rodar.M
#
#
# prep1 = Preprocess1()
# prep1.set_saturation_regions(M)
#
# # m1 = Monophasic(M)
# m1 = Biphasic(M)
# m1.get_transmissibility_matrix_without_contours()
# m1.get_transmissibility_matrix()
# m1.get_RHS_term()
#
#
# solver = SolverSp()
# x = solver.direct_solver(m1.datas['T'], m1.datas['b'])
# m1.get_solution(x)
# m1.get_flux_faces_and_volumes()
#
# pdb.set_trace()
# M.data.update_variables_to_mesh()

from packs.simulations.monophasic_simulation import M

pdb.set_trace()




import pdb; pdb.set_trace()





import pdb; pdb.set_trace()








# import pickle
#
# from tcc.load_save_initialize.load_infos import LoadInfos
# from tcc.dual_mesh.create_dual_mesh import DualMesh1
# import numpy as np
# from . import directories
# import pdb; pdb.set_trace()
#
# # file_name = os.path.join(path_flying, 'mesh_obj.txt')
# # with open(file_name, 'wb') as handle:
# #     pickle.dump(M, handle)
#
#
#
# LoadInfos(M)
# DualMesh1(M)
#
# import pdb; pdb.set_trace()
