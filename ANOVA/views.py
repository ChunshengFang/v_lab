import numpy as np
from django.http import JsonResponse
from vLab.GlycosylationModelBase.GlycosylationNetwork import GlycosylationNetwork
from vLab.GlycosylationModelBase.GlycosylationModelParams import CellCultureVariables, \
    GlycosylationModelParamClass
import os
from vLab.GlycosylationModelBase.GlycosylationDerivative import steady_state_inner_derivative
from vLab.PerfusionSimulator.Utils import compute_species_distribution
from numpy import load
import sys
import pandas as pd
from scipy.integrate import solve_ivp
from scipy.interpolate import interp1d
from django.shortcuts import render
import random




def doe_input(username):
    path_for_login_user = os.path.join("./user_data", username)
    return load(os.path.join(path_for_login_user, 'DOE.npy'))


class ODESolver:

    def __init__(self, t, y0, x, p, fp):
        self.y0 = y0
        self.t = t
        self.x = x
        self.p = p
        self.fp = fp
        self.os = None

    def solve(self):

        # yout = odeint(inner_derivative, self.y0, self.t, args=(self.x, self.p, self.fp,), rtol=1e-4, atol=1e-7) # h0float, (0: solver-determined), optional
        yout = solve_ivp(steady_state_inner_derivative, self.t, self.y0, args=(self.x, self.p, self.fp,), method='BDF',
                         rtol=1e-8, atol=1e-10)  # h0float, (0: solver-determined), optional

        tres = np.linspace(0, 1, 1001)
        os = interp1d(yout.t, yout.y, axis=1)(tres)
        self.os = os[:self.fp.nos, :]  # yout.T[:self.fp.nos, :]
        HM, FA1G1, FA2G0, FA2G1, FA2G2, SIA = compute_species_distribution(self.os)
        return HM, FA1G1, FA2G0, FA2G1, FA2G2, SIA


def ANOVA(request):
    from vLab.GlycosylationModelBase.GlycosylationNetwork import GlycosylationNetwork
    from vLab.GlycosylationModelBase.GlycosylationModelParams import CellCultureVariables, \
        GlycosylationModelParamClass
    username = request.GET.get('username', '')
    if not username:
        return render(request, 'ANOVA.html')
    try:
        macro = 5
        result = []
        for i in range(macro):
            exp_conditions = doe_input(sys.argv[1]).astype(float)
            exp_conditions = {idx + 1: exp_conditions[idx][1:] for idx in range(len(exp_conditions))}
            noise =random.uniform(0, 1)
            fp = GlycosylationNetwork(
                network_data_path='./data/Network Description.csv')  # ../../tests/
            p = GlycosylationModelParamClass(noise=noise / np.sqrt(40))
            x = CellCultureVariables(1.5, 0.01, 0.1198, 66.3856,
                                    np.array([0.490 + 1.452, 0.117 + 0.379, 0.058 + 0.190]) * 1e3,
                                    np.array([1.62, 0.043, 0.1158, 0.040]) * 1e3)
        # compute boundary conditions
            ic = np.zeros((fp.nos + fp.nns + fp.nn))
            ic[0] = x.mabtiter  # umol / L
            ic[
            fp.nos:(fp.nos + fp.nns)] = x.nscyt * 40  # nucleotide sugar concentrations in umol / L.third entry is mystery
            ic[fp.nos + 3] = x.udpgalcyt * 1e3 * 40  # updating with correct UDP-Gal concentration
            ic[(fp.nos + fp.nns):] = x.ncyt  # sum of nucleotide concentrations in umol / L

            t = [0, 1]  # np.linspace(0,1,10001)
            ode_solver = ODESolver(t, ic, x, p, fp)
            HM, FA1G1, FA2G0, FA2G1, FA2G2, SIA = ode_solver.solve()
            for x in ode_solver.os[:, -1]:
                print("{:10.4f}".format(x))
            for k, v in exp_conditions.items():
                print(k)
                Mn, Galactose, Ammonia = v
                fp = GlycosylationNetwork(network_data_path='./data/Network Description.csv')
                p = GlycosylationModelParamClass()
                x = CellCultureVariables(Ammonia, Mn, Galactose / p.kgaludpgal, 66.3856,
                                        np.array([0.490 + 1.452, 0.117 + 0.379, 0.058 + 0.190]) * 1e3,
                                        np.array([1.62, 0.043, 0.1158, 0.040]) * 1e3)
            # compute boundary conditions
                ic = np.zeros((fp.nos + fp.nns + fp.nn))
                ic[0] = x.mabtiter  # umol / L
                ic[fp.nos:(fp.nos + fp.nns)] = x.nscyt * 40  # nucleotide sugar concentrations in umol / L.third entry is mystery
                ic[fp.nos + 3] = x.udpgalcyt * 1e3 * 40  # updating with correct UDP-Gal concentration
                ic[(fp.nos + fp.nns):] = x.ncyt  # sum of nucleotide concentrations in umol / L

                t = [0, 1]  # np.linspace(0,1,10001)
                ode_solver = ODESolver(t, ic, x, p, fp)
                HM, FA1G1, FA2G0, FA2G1, FA2G2, SIA = ode_solver.solve()
                result.extend(list(zip([i] * 6,
                                        [k] * 6,
                                        ['HM', 'FA1G1', 'FA2G0', 'FA2G1', 'FA2G2', 'SIA'],
                                        [HM, FA1G1, FA2G0, FA2G1, FA2G2, SIA])))
        result_df = pd.DataFrame(result, columns=['Replicate', 'Experiment', 'Glycoform', 'Distribution'])
        data = result_df.to_dict(orient='records')
    # Return a JsonResponse
        return JsonResponse(data, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
