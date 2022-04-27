################################################################################
# Utility classes for superconducting linac
# NOTE: For some reason, using python 3 style type annotations causes circular
#       import issues, so leaving as python 2 style for now
################################################################################
from time import sleep
from typing import Dict, List, Type

from epics import PV

import lcls_tools.devices.scLinac.scLinacUtils as utils


class SSA:
    def __init__(self, cavity):
        # type: (Cavity) -> None
        self.cavity: Cavity = cavity
        self.pvPrefix = self.cavity.pvPrefix + "SSA:"

        self.ssaStatusPV: PV = PV(self.pvPrefix + "StatusMsg")
        self.ssaTurnOnPV: PV = PV(self.pvPrefix + "PowerOn")
        self.ssaTurnOffPV: PV = PV(self.pvPrefix + "PowerOff")

        self.ssaCalibrationStartPV: PV = PV(self.pvPrefix + "CALSTRT")
        self.ssaCalibrationStatusPV: PV = PV(self.pvPrefix + "CALSTS")

        self.currentSSASlopePV: PV = PV(self.pvPrefix + "SLOPE")
        self.measuredSSASlopePV: PV = PV(self.pvPrefix + "SLOPE_NEW")

    def turnOn(self):
        self.setPowerState(True)

    def turnOff(self):
        self.setPowerState(False)

    def setPowerState(self, turnOn: bool):
        print("\nSetting SSA power...")

        if turnOn:
            self.ssaTurnOnPV.put(1)
            sleep(7)
            if self.ssaStatusPV != utils.SSA_STATUS_ON_VALUE:
                raise utils.SSAPowerError("Unable to turn on SSA")
        else:
            if self.ssaStatusPV == utils.SSA_STATUS_ON_VALUE:
                self.ssaTurnOffPV.put(1)
                sleep(1)
                if self.ssaStatusPV == utils.SSA_STATUS_ON_VALUE:
                    raise utils.SSAPowerError("Unable to turn off SSA")

        print("SSA power set\n")

    def runCalibration(self):
        """
        Runs the SSA through its range and finds the slope that describes
        the relationship between SSA drive signal and output power
        :return:
        """
        self.setPowerState(True)
        utils.runCalibration(startPV=self.ssaCalibrationStartPV,
                             statusPV=self.ssaCalibrationStatusPV,
                             exception=utils.SSACalibrationError)

        utils.pushAndSaveCalibrationChange(measuredPV=self.measuredSSASlopePV,
                                           currentPV=self.currentSSASlopePV,
                                           lowerLimit=utils.SSA_SLOPE_LOWER_LIMIT,
                                           upperLimit=utils.SSA_SLOPE_UPPER_LIMIT,
                                           pushPV=self.cavity.pushSSASlopePV,
                                           savePV=self.cavity.saveSSASlopePV,
                                           exception=utils.SSACalibrationError)


class Heater:
    def __init__(self, cavity):
        # type: (Cavity) -> None
        self.cavity = cavity
        self.pvPrefix = "CHTR:CM{cm}:1{cav}55:HV:".format(cm=self.cavity.cryomodule.name,
                                                          cav=self.cavity.number)
        self.powerDesPV = PV(self.pvPrefix + "POWER_SETPT")
        self.powerActPV = PV(self.pvPrefix + "POWER")


class Cavity:
    def __init__(self, cavityNum, rackObject):
        # type: (int, Rack) -> None
        """
        Parameters
        ----------
        cavityNum: int cavity number i.e. 1 - 8
        rackObject: the rack object the cavities belong to
        """

        # TODO fix for HLs
        self.length = 1.038

        self.number = cavityNum
        self.rack: Rack = rackObject
        self.cryomodule = self.rack.cryomodule
        self.linac = self.cryomodule.linac

        self.pvPrefix = "ACCL:{LINAC}:{CRYOMODULE}{CAVITY}0:".format(LINAC=self.linac.name,
                                                                     CRYOMODULE=self.cryomodule.name,
                                                                     CAVITY=self.number)
        self.ctePrefix = "CTE:CM{cm}:1{cav}".format(cm=self.cryomodule.name,
                                                    cav=self.number)

        self.ssa = SSA(self)
        self.heater = Heater(self)

        self.pushSSASlopePV: PV = PV(self.pvPrefix + "PUSH_SSA_SLOPE.PROC")
        self.saveSSASlopePV: PV = PV(self.pvPrefix + "SAVE_SSA_SLOPE.PROC")
        self.interlockResetPV: PV = PV(self.pvPrefix + "INTLK_RESET_ALL")

        self.drivelevelPV: PV = PV(self.pvPrefix + "SEL_ASET")

        self.cavityCalibrationStartPV: PV = PV(self.pvPrefix + "PROBECALSTRT")
        self.cavityCalibrationStatusPV: PV = PV(self.pvPrefix + "PROBECALSTS")

        self.currentQLoadedPV: PV = PV(self.pvPrefix + "QLOADED")
        self.measuredQLoadedPV: PV = PV(self.pvPrefix + "QLOADED_NEW")
        self.pushQLoadedPV: PV = PV(self.pvPrefix + "PUSH_QLOADED.PROC")
        self.saveQLoadedPV: PV = PV(self.pvPrefix + "SAVE_QLOADED.PROC")

        self.currentCavityScalePV: PV = PV(self.pvPrefix + "CAV:SCALER_SEL.B")
        self.measuredCavityScalePV: PV = PV(self.pvPrefix + "CAV:CAL_SCALEB_NEW")
        self.pushCavityScalePV: PV = PV(self.pvPrefix + "PUSH_CAV_SCALE.PROC")
        self.saveCavityScalePV: PV = PV(self.pvPrefix + "SAVE_CAV_SCALE.PROC")

        self.selAmplitudeDesPV: PV = PV(self.pvPrefix + "ADES")
        self.selAmplitudeActPV: PV = PV(self.pvPrefix + "AACTMEAN")

        self.rfModeCtrlPV: PV = PV(self.pvPrefix + "RFMODECTRL")
        self.rfModePV: PV = PV(self.pvPrefix + "RFMODE")

        self.rfStatePV: PV = PV(self.pvPrefix + "RFSTATE")
        self.rfControlPV: PV = PV(self.pvPrefix + "RFCTRL")

        self.pulseGoButtonPV: PV = PV(self.pvPrefix + "PULSE_DIFF_SUM")
        self.pulseStatusPV = PV(self.pvPrefix + "PULSE_STATUS")
        self.pulseOnTimePV: PV = PV(self.pvPrefix + "PULSE_ONTIME")

        self.revWaveformPV: PV = PV(self.pvPrefix + "REV:AWF")
        self.fwdWaveformPV: PV = PV(self.pvPrefix + "FWD:AWF")
        self.cavWaveformPV: PV = PV(self.pvPrefix + "CAV:AWF")

    def checkAndSetOnTime(self):
        """
        In pulsed mode the cavity has a duty cycle determined by the on time and
        off time. We want the on time to be 70 ms or else the various cavity
        parameters calculated from the waveform (e.g. the RF gradient) won't be
        accurate.
        :return:
        """
        print("Checking RF Pulse On Time...")
        if self.pulseOnTimePV.value != utils.NOMINAL_PULSED_ONTIME:
            print("Setting RF Pulse On Time to {ontime} ms".format(ontime=utils.NOMINAL_PULSED_ONTIME))
            self.pulseOnTimePV.put(utils.NOMINAL_PULSED_ONTIME)
            self.pushGoButton()

    def pushGoButton(self):
        """
        Many of the changes made to a cavity don't actually take effect until the
        go button is pressed
        :return:
        """
        self.pulseGoButtonPV.put(1)
        while self.pulseStatusPV.value < 2:
            sleep(1)
        if self.pulseStatusPV.value > 2:
            raise utils.PulseError("Unable to pulse cavity")

    def turnOn(self):
        self.setPowerState(True)

    def turnOff(self):
        self.setPowerState(False)

    def setPowerState(self, turnOn: bool):
        """
        Turn the cavity on or off
        :param turnOn:
        :return:
        """
        desiredState = (1 if turnOn else 0)

        if self.rfStatePV.value != desiredState:
            print("\nSetting RF State...")
            self.rfControlPV.put(desiredState)

        print("RF state set\n")

    def runCalibration(self, loadedQLowerlimit=utils.LOADED_Q_LOWER_LIMIT,
                       loadedQUpperlimit=utils.LOADED_Q_UPPER_LIMIT):
        """
        Calibrates the cavity's RF probe so that the amplitude readback will be
        accurate. Also measures the loaded Q (quality factor) of the cavity power
        coupler
        :return:
        """
        self.interlockResetPV.put(1)
        sleep(2)

        self.drivelevelPV.put(15)

        utils.runCalibration(startPV=self.cavityCalibrationStartPV,
                             statusPV=self.cavityCalibrationStatusPV,
                             exception=utils.CavityQLoadedCalibrationError)

        utils.pushAndSaveCalibrationChange(measuredPV=self.measuredQLoadedPV,
                                           currentPV=self.currentQLoadedPV,
                                           lowerLimit=loadedQLowerlimit,
                                           upperLimit=loadedQUpperlimit,
                                           pushPV=self.pushQLoadedPV,
                                           savePV=self.saveQLoadedPV,
                                           exception=utils.CavityQLoadedCalibrationError)

        utils.pushAndSaveCalibrationChange(measuredPV=self.measuredCavityScalePV,
                                           currentPV=self.currentCavityScalePV,
                                           lowerLimit=utils.CAVITY_SCALE_LOWER_LIMIT,
                                           upperLimit=utils.CAVITY_SCALE_UPPER_LIMIT,
                                           pushPV=self.pushCavityScalePV,
                                           savePV=self.saveCavityScalePV,
                                           exception=utils.CavityScaleFactorCalibrationError)


class Magnet:
    def __init__(self, magnettype, cryomodule):
        # type: (str, Cryomodule) -> None
        self.pvprefix = "{magnettype}:{linac}:{cm}85:".format(magnettype=magnettype,
                                                              linac=cryomodule.linac.name,
                                                              cm=cryomodule.name)


class Rack:
    def __init__(self, rackName, cryoObject, cavityClass=Cavity):
        # type: (str, Cryomodule, Type[Cavity]) -> None
        """
        Parameters
        ----------
        rackName: str name of rack (always either "A" or "B")
        cryoObject: the cryomodule object this rack belongs to
        cavityClass: cavity object
        """

        self.cryomodule = cryoObject
        self.rackName = rackName
        self.cavities = {}
        self.pvPrefix = self.cryomodule.pvPrefix + "RACK{RACK}:".format(RACK=self.rackName)

        if rackName == "A":
            # rack A always has cavities 1 - 4
            for cavityNum in range(1, 5):
                self.cavities[cavityNum] = cavityClass(cavityNum, self)

        elif rackName == "B":
            # rack B always has cavities 5 - 8
            for cavityNum in range(5, 9):
                self.cavities[cavityNum] = cavityClass(cavityNum, self)

        else:
            raise Exception("Bad rack name")


class Cryomodule:

    def __init__(self, cryoName, linacObject, cavityClass=Cavity, magnetClass=Magnet, rackClass=Rack):
        # type: (str, Linac, Type[Cavity], Type[Magnet], Type[Rack]) -> None
        """
        Parameters
        ----------
        cryoName: str name of Cryomodule i.e. "02", "03", "H1", "H2"
        linacObject: the linac object this cryomodule belongs to i.e. CM02 is in linac L1B
        cavityClass: cavity object
        """

        self.name = cryoName
        self.linac = linacObject
        self.quad = magnetClass("QUAD", self)
        self.xcor = magnetClass("XCOR", self)
        self.ycor = magnetClass("YCOR", self)

        self.pvPrefix = "ACCL:{LINAC}:{CRYOMODULE}00:".format(LINAC=self.linac.name,
                                                              CRYOMODULE=self.name)
        self.ctePrefix = "CTE:CM{cm}:".format(cm=self.name)
        self.cvtPrefix = "CVT:CM{cm}:".format(cm=self.name)
        self.cpvPrefix = "CPV:CM{cm}:".format(cm=self.name)
        self.jtPrefix = "CLIC:CM{cm}:3001:PVJT:".format(cm=self.name)

        self.dsLevelPV: PV = PV("CLL:CM{cm}:2301:DS:LVL")
        self.usLevelPV: PV = PV("CLL:CM{cm}:2601:US:LVL")

        self.racks = {"A": rackClass("A", self, cavityClass),
                      "B": rackClass("B", self, cavityClass)}

        self.cavities: Dict[int, cavityClass] = {}
        self.cavities.update(self.racks["A"].cavities)
        self.cavities.update(self.racks["B"].cavities)


class Linac:
    def __init__(self, linacName, cryomoduleStringList, cavityClass=Cavity, cryomoduleClass=Cryomodule, rackClass=Rack,
                 magnetClass=Magnet):
        # type: (str, List[str], Type[Cavity], Type[Cryomodule], Type[Rack], Type[Magnet]) -> None
        """
        Parameters
        ----------
        linacName: str name of Linac i.e. "L0B", "L1B", "L2B", "L3B"
        cryomoduleStringList: list of string names of cryomodules in the linac
        cavityClass: cavity object
        """

        self.name = linacName
        self.cryomodules: Dict[str, cryomoduleClass] = {}
        for cryomoduleString in cryomoduleStringList:
            self.cryomodules[cryomoduleString] = cryomoduleClass(cryoName=cryomoduleString, linacObject=self,
                                                                 cavityClass=cavityClass, rackClass=rackClass,
                                                                 magnetClass=magnetClass)


# Global list of superconducting linac objects
L0B = ["01"]
L1B = ["02", "03", "H1", "H2"]
L2B = ["04", "05", "06", "07", "08", "09", "10", "11", "12", "13", "14", "15"]
L3B = ["16", "17", "18", "19", "20", "21", "22", "23", "24", "25", "26", "27",
       "28", "29", "30", "31", "32", "33", "34", "35"]

LINAC_TUPLES = [("L0B", L0B), ("L1B", L1B), ("L2B", L2B), ("L3B", L3B)]

# Utility list of linacs
LINAC_OBJECTS: List[Linac] = []

# Utility dictionary to map cryomodule name strings to cryomodule objects
CRYOMODULE_OBJECTS: Dict[str, Cryomodule] = {}

for idx, (name, cryomoduleList) in enumerate(LINAC_TUPLES):
    linac = Linac(name, cryomoduleList)
    LINAC_OBJECTS.append(linac)
    CRYOMODULE_OBJECTS.update(linac.cryomodules)
