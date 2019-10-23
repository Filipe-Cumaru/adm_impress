import scipy.sparse as sp
from scipy.sparse import linalg


class SolverSp:

    def __init__(self):
        pass

    def direct_solver(self, A, b):

        A2 = A.tocsc().copy()

        solution = linalg.spsolve(A2,b)

        return solution

    def lu_solver(self, A, b):

        A2 = A.tocsc().copy()

        LU = linalg.splu(A2)
        solution = LU.solve(b)

        return solution

    def gmres_solver(self, A, b, x0=None, tol=1e-5, precond=None):
        n = A.shape[0]
        if precond:
            # M1 = linalg.spilu(A)
            # M_x = lambda x: M1.solve(x)

            M_x = lambda x: linalg.spsolve(A, x)
            M = linalg.LinearOperator((n, n), M_x)
        else:
            M = None

        x, exitcode = linalg.gmres(A, b, x0=x0, tol=tol, M=M)

        return x
