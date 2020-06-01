import numpy as np
from cmath import acos
from ..utils import constants as ctes
from ..solvers.EOS_solver.solver import CubicRoots

class PengRobinson:
    def __init__(self, P, T, kprop):
        self.P = P
        self.T = T
        self.coefficientsPR(kprop)

    def coefficientsPR(self, kprop):
        #l - any phase molar composition
        PR_kC7 = np.array([0.379642, 1.48503, 0.1644, 0.016667])
        PR_k = np.array([0.37464, 1.54226, 0.26992])

        k = (PR_kC7[0] + PR_kC7[1] * kprop.w - PR_kC7[2] * kprop.w ** 2 + \
            PR_kC7[3] * kprop.w ** 3) * (1*(kprop.w >= 0.49))  + (PR_k[0] + PR_k[1] * kprop.w - \
            PR_k[2] * kprop.w ** 2) * (1*(kprop.w < 0.49))
        alpha = (1 + k * (1 - (self.T/ kprop.Tc) ** (1 / 2))) ** 2
        aalpha_i = 0.45724 * (ctes.R * kprop.Tc) ** 2 / kprop.Pc * alpha
        self.b = 0.07780 * ctes.R * kprop.Tc / kprop.Pc
        aalpha_i_reshape = np.ones((kprop.Nc,kprop.Nc)) * aalpha_i[:,np.newaxis]
        self.aalpha_ij = np.sqrt(aalpha_i_reshape.T * aalpha_i[:,np.newaxis]) \
                        * (1 - kprop.Bin)

    def coefficients_cubic_EOS(self, kprop, l):
        self.bm = sum(l * self.b)
        l_reshape = np.ones((self.aalpha_ij).shape) * l[:, np.newaxis]
        self.aalpha = (l_reshape.T * l[:,np.newaxis] * self.aalpha_ij).sum()
        B = self.bm * self.P/ (ctes.R* self.T)
        A = self.aalpha * self.P/ (ctes.R* self.T) ** 2
        self.psi = (l_reshape * self.aalpha_ij).sum(axis = 0)
        return A, B

    def Z(B, A, ph):
        # PR cubic EOS: Z**3 - (1-B)*Z**2 + (A-2*B-3*B**2)*Z-(A*B-B**2-B**3)
        coef = [1, -(1 - B), (A - 2*B - 3*B**2), -(A*B - B**2 - B**3)]
        Z = np.roots(coef)
        root = np.isreal(Z) # return True for real roots
        #position where the real roots are - crated for organization only
        real_roots_position = np.where(root == True)
        Z_reais = np.real(Z[real_roots_position[:]]) #Saving the real roots
        Z = min(Z_reais) * ph + max(Z_reais) * (1 - ph)
        ''' This last line, considers that the phase is composed by a pure
         component, so the EOS model can return more than one real root.
            If liquid, Zl = min(Z) and gas, Zv = max(Z).
            You can notice that, if there's only one real root,
        it works as well.'''
        return Z_reais

    def lnphi(self, kprop, l, ph):
        #l - any phase molar composition
        l = l[:,np.newaxis]
        A, B = self.coefficients_cubic_EOS_vectorized(kprop,l)
        Z = PengRobinson.Z_vectorized(A, B)
        Z = min(Z) * ph + max(Z) * (1 - ph)
        lnphi = self.b / self.bm * (Z - 1) - np.log(Z - B) - A / (2 * (2 ** (1/2))
                * B) * (2 * self.psi / self.aalpha - self.b / self.bm) * np.log((Z + (1 +
                2 ** (1/2)) * B) / (Z + (1 - 2 ** (1/2)) * B))

        return lnphi

    """ Bellow is showed two functions of the PR EOS equation, that were constructed in a vectorized manner.
    This means that, when possible to obtain everything just once, I will use these two functions. For now, I'm
    using them in the other_properties functions, once x and y are calculated by that time."""

    def coefficients_cubic_EOS_vectorized(self, kprop, l):
        self.bm = np.sum(l * self.b[:,np.newaxis], axis=0)
        l_reshape = np.ones((self.aalpha_ij).shape)[:,:,np.newaxis] * l[:,np.newaxis,:]
        self.aalpha = (l_reshape * l[np.newaxis,:,:] * self.aalpha_ij[:,:,np.newaxis]).sum(axis=0).sum(axis=0)
        B = self.bm * self.P / (ctes.R* self.T)
        A = self.aalpha * self.P / (ctes.R* self.T) ** 2
        self.psi = (l_reshape * self.aalpha_ij).sum(axis = 0)
        return A, B

    def Z_vectorized(A, B):
        coef = np.empty([4,len(B.ravel())])
        coef[0,:] = np.ones(len(B))
        coef[1,:] = -(1 - B)
        coef[2,:] = (A - 2*B - 3*B**2)
        coef[3,:] = -(A*B - B**2 - B**3)
        Z = CubicRoots().run(coef)
        return Z