# -*- coding: utf-8 -*-
"""
Created on 22 Feb 2013

@author: Rinze de Laat

Copyright © 2013 Rinze de Laat, Delmic

This file is part of Odemis.

Odemis is free software: you can redistribute it and/or modify it under the
terms of the GNU General Public License as published by the Free Software
Foundation, either version 2 of the License, or (at your option) any later
version.

Odemis is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
Odemis. If not, see http://www.gnu.org/licenses/.


### Purpose ###

This module contains classes that describe Streams, which are basically
Detector, Emitter and Dataflow associations.

"""

from __future__ import division

import logging
import inspect

import numpy
from numpy.polynomial import polynomial
from wx.lib.pubsub import pub

from odemis import model
from odemis.gui import util
from odemis.model import VigilantAttribute, VigilantAttributeBase, \
    MD_POS, MD_PIXEL_SIZE, MD_SENSOR_PIXEL_SIZE, MD_WL_POLYNOMIAL
from odemis.gui.model.img import InstrumentalImage


# to identify a ROI which must still be defined by the user
UNDEFINED_ROI = (0, 0, 0, 0)

class Stream(object):
    """ A stream combines a Detector, its associated Dataflow and an Emitter.

    It handles acquiring the data from the hardware and renders it as an
    InstrumentalImage with the given image transformation.

    This is an abstract class, unless the emitter doesn't need any configuration
    (always on, with the right settings).

    Note: If a Stream needs multiple Emitters, then this should be implemented in
    a subclass of Stream.
    """

    WARNING_EXCITATION_NOT_OPT = ("The excitation wavelength selected cannot "
                                  "be optimally generated by the hardware.")
    WARNING_EXCITATION_IMPOSSIBLE = ("The excitation wavelength selected "
                                     "cannot be generated by the hardware.")
    WARNING_EMISSION_NOT_OPT = ("The emission wavelength selected cannot be "
                                "optimally detected by the hardware.")
    WARNING_EMISSION_IMPOSSIBLE = ("The emission wavelength selected cannot be "
                                   "detected by the hardware.")

    # Minimum overhead time in seconds when acquiring an image
    SETUP_OVERHEAD = 0.1

    def __init__(self, name, detector, dataflow, emitter):
        """
        name (string): user-friendly name of this stream
        detector (Detector): the detector which has the dataflow
        dataflow (Dataflow): the dataflow from which to get the data
        emitter (Emitter): the emitter
        """

        self.name = model.StringVA(name)

        # Hardware Components
        self._detector = detector
        self._emitter = emitter

        # Dataflow (Live image stream with meta data)
        # Note: A Detectors can have multiple dataflows, so that's why a Stream
        # has a separate attribute.
        self._dataflow = dataflow

        # list of DataArray received and used to generate the image
        # every time it's modified, image is also modified
        self.raw = []
        # the most important attribute
        self.image = VigilantAttribute(InstrumentalImage(None))

        # TODO: should maybe to 2 methods activate/deactivate to explicitly
        # start/stop acquisition, and one VA "updated" to stated that the user
        # want this stream updated (as often as possible while other streams are
        # also updated)
        self.should_update = model.BooleanVA(False)
        self.is_active = model.BooleanVA(False)
        self.is_active.subscribe(self.onActive)

        # Region of interest as left, top, right, bottom (in ratio from the
        # whole area of the emitter => between 0 and 1)
        self.roi = model.TupleContinuous((0, 0, 1, 1),
                                         range=[(0, 0, 0, 0), (1, 1, 1, 1)],
                                         cls=(int, long, float))

        self._depth = 0

        if self._detector:
            # The last element of the shape indicates the bit depth, which
            # is used for brightness/contrast adjustment.
            self._depth = self._detector.shape[-1]

        # whether to use auto brightness & contrast
        self.auto_bc = model.BooleanVA(True)

        # these 2 are only used if auto_bc is False
        # ratio, contrast if no auto
        self.contrast = model.FloatContinuous(0, range=[-100, 100])
        # ratio, balance if no auto
        self.brightness = model.FloatContinuous(0, range=[-100, 100])

        self.auto_bc.subscribe(self.onAutoBC)
        self.contrast.subscribe(self.onBrightnessContrast)
        self.brightness.subscribe(self.onBrightnessContrast)

        # list of warnings to display to the user
        # TODO should be a set
        self.warnings = model.ListVA([]) # should only contains WARNING_*

    def estimateAcquisitionTime(self):
        """ Estimate the time it will take to acquire one image with the current
        settings of the detector and emitter.

        returns (float): approximate time in seconds that acquisition will take
        """
        # This default implementation returns the shortest possible time, taking
        # into account a minimum overhead. (As in, acquisition will never take
        # less than 0.1 seconds)
        return self.SETUP_OVERHEAD

    def _removeWarnings(self, *warnings):
        """ Remove all the given warnings if any are present

        warnings (set of WARNING_*): the warnings to remove
        """
        new_warnings = set(self.warnings.value) - set(warnings)
        self.warnings.value = list(new_warnings)

    def _addWarning(self, warning):
        """ Add a warning if not already present

        warning (WARNING_*): the warning to add
        """
        if not warning in self.warnings.value:
            self.warnings.value.append(warning)

    def onActive(self, active):
        """ Called when the Stream is activated or deactivated by setting the
        is_active attribute
        """
        if active:
            logging.debug("Subscribing to dataflow of component %s", self._detector.name)
            if not self.should_update.value:
                logging.warning("Trying to activate stream while it's not supposed to update")
            self._dataflow.subscribe(self.onNewImage)
        else:
            logging.debug("Unsubscribing from dataflow of component %s", self._detector.name)
            self._dataflow.unsubscribe(self.onNewImage)

    # No __del__: subscription should be automatically stopped when the object
    # disappears, and the user should stop the update first anyway.

    def _updateImage(self, tint=(255, 255, 255)):
        """ Recomputes the image with all the raw data available

        tint ((int, int, int)): colouration of the image, in RGB. Only used by
            FluoStream to avoid code duplication
        """
        data = self.raw[0]

        if self.auto_bc.value:
            brightness = None
            contrast = None
        else:
            brightness = self.brightness.value / 100
            contrast = self.contrast.value / 100

        im = util.img.DataArray2wxImage(data,
                                        self._depth,
                                        brightness,
                                        contrast,
                                        tint)
        im.InitAlpha() # it's a different buffer so useless to do it in numpy

        try:
            pos = data.metadata[MD_POS]
        except KeyError:
            logging.warning("Position of image unknown")
            pos = (0, 0)

        try:
            mpp = data.metadata[MD_PIXEL_SIZE][0]
        except KeyError:
            logging.warning("pixel density of image unknown")
            # Hopefully it'll be within the same magnitude
            mpp = data.metadata[MD_SENSOR_PIXEL_SIZE][0] / 10

        self.image.value = InstrumentalImage(im, mpp, pos)

    def onAutoBC(self, enabled):
        if self.raw:
            # if changing to manual: need to set the current (automatic) B/C
            if enabled == False:
                b, c = util.img.FindOptimalBC(self.raw[0], self._depth)
                self.brightness.value = b * 100
                self.contrast.value = c * 100
            else:
                # B/C might be different from the manual values => redisplay
                self._updateImage()

    def onBrightnessContrast(self, unused):
        # called whenever brightness/contrast changes
        # => needs to recompute the image (but not too often, so we do it in a timer)

        if self.raw:
            self._updateImage()

    def onNewImage(self, dataflow, data):
        # For now, raw images are pretty simple: we only have one
        # (in the future, we could keep the old ones which are not fully overlapped
        if self.raw:
            self.raw.pop()
        self.raw.insert(0, data)
        self._updateImage()

    def show_vigilant_attributes(self):
        vas = inspect.getmembers(
                    self,
                    lambda x: isinstance(x, VigilantAttributeBase)
        )

        print vas



class SEMStream(Stream):
    """ Stream containing images obtained via Scanning electron microscope.

    It basically knows how to activate the scanning electron and the detector.
    """
    def __init__(self, name, detector, dataflow, emitter):
        Stream.__init__(self, name, detector, dataflow, emitter)
        
        # TODO: drift correction
        # .driftCorrection: Boolean
        # .driftROI: the region used for the drift correction
        # .driftCorrectionPeriod: time in s between each correction (approximate,
        #   tries to do it after every N lines, or every N pixels) 
        # Need to see  
        
        try:
            self._prevDwellTime = emitter.dwellTime.value
            emitter.dwellTime.subscribe(self.onDwellTime)
        except AttributeError:
            # if emitter has no dwell time -> no problem
            pass

    def estimateAcquisitionTime(self):

        try:
            res = list(self._emitter.resolution.value)
            # Typically there is few more pixels inserted at the beginning of each
            # line for the settle time of the beam. We guesstimate by just adding
            # 1 pixel to each line
            if len(res) == 2:
                res[1] += 1
            else:
                logging.warning(("Resolution of scanner is not 2 dimensional, "
                                 "time estimation might be wrong"))
            # Each pixel x the dwell time in seconds
            duration = self._emitter.dwellTime.value * numpy.prod(res)
            # Add the setup time
            duration += self.SETUP_OVERHEAD

            return duration
        except:
            msg = "Exception while estimating acquisition time of %s"
            logging.exception(msg, self.name.value)
            return Stream.estimateAcquisitionTime(self)

    def onActive(self, active):
        if active:
            # TODO: if can blank => unblank
            pass
        Stream.onActive(self, active)

    def onDwellTime(self, value):
        # When the dwell time changes, the new value is only used on the next
        # acquisition. Assuming the change comes from the user (very likely),
        # then if the current acquisition would take a long time, cancel it, and
        # restart acquisition so that the new value is directly used. The main
        # goal is to avoid cases where user mistakenly put a 10+ s acquisition,
        # and it takes ages to get back to a faster acquisition. Note: it only
        # works if we are the only subscriber (but that's very likely).

        try:
            if self.is_active.value == False:
                # not acquiring => nothing to do
                return

            # approximate time for the current image acquisition
            res = self._emitter.resolution.value
            prevDuration = self._prevDwellTime * numpy.prod(res)

            if prevDuration < 1:
                # very short anyway, not worthy
                return

            # TODO: do this on a rate-limited fashion (now, or ~1s)
            # unsubscribe, and re-subscribe immediately
            self._dataflow.unsubscribe(self.onNewImage)
            self._dataflow.subscribe(self.onNewImage)

        finally:
            self._prevDwellTime = value

class CameraStream(Stream):
    """ Abstract class representing streams which have a digital camera as a
    detector.

    Mostly used to share time estimation only.
    """
    def estimateAcquisitionTime(self):
        # exposure time + readout time * pixels (if CCD) + set-up time
        try:
            exp = self._detector.exposureTime.value
            res = self._detector.resolution.value
            if isinstance(self._detector.readoutRate, model.VigilantAttributeBase):
                readout = 1 / self._detector.readoutRate.value
            else:
                # let's assume it's super fast
                readout = 0

            duration = exp + numpy.prod(res) * readout + self.SETUP_OVERHEAD
            return duration
        except:
            msg = "Exception while estimating acquisition time of %s"
            logging.exception(msg, self.name.value)
            return Stream.estimateAcquisitionTime(self)

class BrightfieldStream(CameraStream):
    """ Stream containing images obtained via optical brightfield illumination.

    It basically knows how to select white light and disable any filter.
    """

    def onActive(self, active):
        if active:
            self._setLightExcitation()
            # TODO: do we need to have a special command to disable filter??
            # or should it be disabled automatically by the other streams not
            #using it?
            # self._set_emission_filter()
        Stream.onActive(self, active)

    # def _set_emission_filter(self):
    #     if not self._filter.band.readonly:
    #         raise NotImplementedError("Do not know how to change filter band")

    def _setLightExcitation(self):
        # TODO: how to select white light??? We need a brightlight hardware?
        # Turn on all the sources? Does this always mean white?
        # At least we should set a warning if the final emission range is quite
        # different from the normal white spectrum
        em = [1] * len(self._emitter.emissions.value)
        self._emitter.emissions.value = em


class FluoStream(CameraStream):
    """ Stream containing images obtained via epifluorescence.

    It basically knows how to select the right emission/filtered wavelengths,
    and how to taint the image.

    Note: Excitation is (filtered) light comming from a light source and
    emission is the light emitted by the sample.
    """

    def __init__(self, name, detector, dataflow, emitter, em_filter):
        """
        name (string): user-friendly name of this stream
        detector (Detector): the detector which has the dataflow
        dataflow (Dataflow): the dataflow from which to get the data
        emitter (Light): the HwComponent to modify the light excitation
        filter (Filter): the HwComponent to modify the emission light filtering
        """
        CameraStream.__init__(self, name, detector, dataflow, emitter)
        self._em_filter = em_filter

        # This is what is displayed to the user
        # TODO: what should be nice default value of the light and filter?
        exc_range = [min([s[0] for s in emitter.spectra.value]),
                     max([s[4] for s in emitter.spectra.value])]
        self.excitation = model.FloatContinuous(488e-9, range=exc_range, unit="m")
        self.excitation.subscribe(self.onExcitation)

        em_range = [min([s[0] for s in em_filter.band.value]),
                    max([s[1] for s in em_filter.band.value])]
        self.emission = model.FloatContinuous(507e-9, range=em_range, unit="m")
        self.emission.subscribe(self.onEmission)

        # colouration of the image
        defaultTint = util.conversion.wave2rgb(self.emission.value)
        self.tint = model.ListVA(defaultTint, unit="RGB") # 3-tuple R,G,B
        self.tint.subscribe(self.onTint)

    def onActive(self, active):
        # TODO update Emission or Excitation only if the stream is active
        if active:
            self._setLightExcitation()
            self._set_emission_filter()
        Stream.onActive(self, active)

    def _updateImage(self): #pylint: disable=W0221
        Stream._updateImage(self, self.tint.value)

    def onExcitation(self, value):
        if self.is_active.value:
            self._setLightExcitation()

    def onEmission(self, value):
        if self.is_active.value:
            self._set_emission_filter()

    def onTint(self, value):
        if self.raw:
            self._updateImage()

    def _set_emission_filter(self):
        """ Check if the emission value matches the emission filter band

        TODO: Change name of method, since no filter is actually set?
        """

        wave_length = self.emission.value

        # TODO: we need a way to know if the HwComponent can change
        # automatically or only manually. For now we suppose it's manual

        # Changed manually: we can only check that it's correct
        fitting = False
        for l, h in self._em_filter.band.value:
            if l < wave_length < h:
                fitting = True
                break

        self._removeWarnings(Stream.WARNING_EMISSION_IMPOSSIBLE,
                             Stream.WARNING_EMISSION_NOT_OPT)
        if not fitting:
            logging.warning("Emission wavelength %s doesn't fit the filter",
                            util.units.readable_str(wave_length, "m"))
            self._addWarning(Stream.WARNING_EMISSION_IMPOSSIBLE)
            # TODO: detect no optimal situation (within 10% band of border?)
        return

    def _setLightExcitation(self):
        """ TODO: rename method to better match what the code does """

        wave_length = self.excitation.value

        def quantify_fit(wl, spec):
            """ Quantifies how well the given wave length matches the given
            spectrum: the better the match, the higher the return value will be.

            wl (float): Wave length to quantify
            spec (5-tuple float): The spectrum to check the wave length against
            """

            if spec[0] < wl < spec[4]:
                distance = abs(wl - spec[2]) # distance to 100%
                if distance:
                    return 1 / distance
                # No distance, ultimate match
                return float("inf")
            else:
                # No match
                return 0

        spectra = self._emitter.spectra.value
        # arg_max with quantify_fit function as key
        best = max(spectra, key=lambda x: quantify_fit(wave_length, x))
        i = spectra.index(best)

        # create an emissions with only one source active, which best matches
        # the excitation wave length
        emissions = [0] * len(spectra)
        emissions[i] = 1
        self._emitter.emissions.value = emissions

        # TODO: read back self._emitter.emissions.value to get the actual value
        # set warnings if necessary
        self._removeWarnings(Stream.WARNING_EXCITATION_IMPOSSIBLE,
                             Stream.WARNING_EXCITATION_NOT_OPT)

        # TODO: if the band is too wide (e.g., white), it should also have a
        # warning
        # TODO: if the light can only be changed manually, display a warning
        if wave_length < best[0] or wave_length > best[4]:
            # outside of band
            self._addWarning(Stream.WARNING_EXCITATION_IMPOSSIBLE)
        elif wave_length < best[1] or wave_length > best[3]:
            # outside of main 50% band
            self._addWarning(Stream.WARNING_EXCITATION_NOT_OPT)


class SpectrumStream(Stream):
    """
    A Spectrum stream. Be aware that acquisition can be very long so should
    not be used for live view. So it has no .image (for now).
    See StaticSpectrumStream for displaying a stream.
    """

    def __init__(self, name, detector, dataflow, emitter):
        self.name = model.StringVA(name)

        # Hardware Components
        self._detector = detector # the spectrometer
        self._emitter = emitter # the e-beam
        # To acquire simultaneously other detector (ex: SEM secondary electrons)
        # a separate stream must be used, and the acquisition manager will take
        # care of doing both at the same time

        # data-flow of the spectrometer
        self._dataflow = dataflow

        # all the information needed to acquire an image (in addition to the
        # hardware component settings which can be directly set).

        # Region of interest as left, top, right, bottom (in ratio from the
        # whole area of the emitter => between 0 and 1)
        self.roi = model.TupleContinuous((0, 0, 1, 1),
                                         range=[(0, 0, 0, 0), (1, 1, 1, 1)],
                                         cls=(int, long, float))
        # the number of pixels acquired in each dimension
        # it will be assigned to the resolution of the emitter (but cannot be
        # directly set, as one might want to use the emitter while configuring
        # the stream).
        self.repetition = model.ResolutionVA(emitter.resolution.value,
                                             emitter.resolution.range)

        # exposure time of each pixel is the exposure time of the detector,
        # the dwell time of the emitter will be adapted before acquisition.
        
        # FIXME: we should do the opposite, the interface controller updates this
        # value when needed
        pub.subscribe(self.on_selection_changed, 'sparc.acq.selection.changed')

    def on_selection_changed(self, region_of_interest):
        #self.roi.value = region_of_interest or self._default_roi
        self.roi.value = UNDEFINED_ROI

    def estimateAcquisitionTime(self):
        try:
            res = list(self.repetition.value)
            # Typically there is few more pixels inserted at the beginning of each
            # line for the settle time of the beam. We guesstimate by just adding
            # 1 pixel to each line
            if len(res) == 2:
                res[1] += 1
            else:
                logging.warning(("Resolution of scanner is not 2 dimensional, "
                                 "time estimation might be wrong"))

            # Each pixel x the exposure time (of the detector) + readout time + 10% overhead
            exp = self._detector.exposureTime.value
            try:
                ro_rate = self._detector.readoutRate.value
                readout = numpy.prod(self._detector.resolution.value) / ro_rate
            except:
                readout = 0
            duration = (exp + readout) * numpy.prod(res) * 1.10
            # Add the setup time
            duration += self.SETUP_OVERHEAD

            return duration
        except:
            msg = "Exception while estimating acquisition time of %s"
            logging.exception(msg, self.name.value)
            return Stream.estimateAcquisitionTime(self)

class ARStream(Stream):
    """
    An angular-resolved stream. Be aware that acquisition can be very long so should
    not be used for live view. So it has no .image (for now).
    See StaticARStream for displaying a stream.
    """

    def __init__(self, name, detector, dataflow, emitter):
        self.name = model.StringVA(name)

        # Hardware Components
        self._detector = detector # the CCD
        self._emitter = emitter # the e-beam
        # To acquire simultaneously other detector (ex: SEM secondary electrons)
        # a separate stream must be used, and the acquisition manager will take
        # care of doing both at the same time

        # data-flow of the spectrometer
        self._dataflow = dataflow

        # all the information needed to acquire an image (in addition to the
        # hardware component settings which can be directly set).


        # Region of interest as left, top, right, bottom (in ratio from the
        # whole area of the emitter => between 0 and 1)
        self.roi = model.TupleContinuous((0, 0, 1, 1),
                                         range=[(0, 0, 0, 0), (1, 1, 1, 1)],
                                         cls=(int, long, float))
        # the number of pixels acquired in each dimension
        # it will be assigned to the resolution of the emitter (but cannot be
        # directly set, as one might want to use the emitter while configuring
        # the stream).
        self.repetition = model.ResolutionVA(emitter.resolution.value,
                                             emitter.resolution.range)

        # exposure time of each pixel is the exposure time of the detector,
        # the dwell time of the emitter will be adapted before acquisition.

    def estimateAcquisitionTime(self):
        try:
            res = list(self.repetition.value)
            # Typically there is few more pixels inserted at the beginning of each
            # line for the settle time of the beam. We guesstimate by just adding
            # 1 pixel to each line
            if len(res) == 2:
                res[1] += 1
            else:
                logging.warning(("Resolution of scanner is not 2 dimensional, "
                                 "time estimation might be wrong"))

            # Each pixel x the exposure time (of the detector) + readout time + 10% overhead
            exp = self._detector.exposureTime.value
            try:
                ro_rate = self._detector.readoutRate.value
                readout = numpy.prod(self._detector.resolution.value) / ro_rate
            except:
                readout = 0
            duration = (exp + readout) * numpy.prod(res) * 1.10
            # Add the setup time
            duration += self.SETUP_OVERHEAD

            return duration
        except:
            msg = "Exception while estimating acquisition time of %s"
            logging.exception(msg, self.name.value)
            return Stream.estimateAcquisitionTime(self)

class StaticStream(Stream):
    """ Stream containing one static image.

    For testing and static images.
    """

    def __init__(self, name, image):
        """
        Note: parameters are different from the base class.
        image (InstrumentalImage or DataArray): image to display or raw data.
          If it is a DataArray, the metadata should contain at least MD_POS and
          MD_PIXEL_SIZE.
        """
        Stream.__init__(self, name, None, None, None)
        if isinstance(image, InstrumentalImage):
            # TODO: use original image as raw, to allow changing the B/C/tint
            self.image = VigilantAttribute(image)
        else: # raw data
            try:
                self._depth = 2**image.metadata[model.MD_BPP]
            except KeyError: # no MD_MPP
                # guess out of the data
                self._depth = image.max()
                minv = image.min()
                if minv < 0:  # signed?
                    self._depth += -minv
                    # FIXME: probably need to fix DataArray2wxImage() for such cases

            self.onNewImage(None, image)

    def onActive(self, active):
        # don't do anything
        pass

class StaticSEMStream(StaticStream):
    """
    Same as a StaticStream, but considered a SEM stream
    """
    pass

# Different projection types
# TODO: maybe ONE_POINT can be dropped (= LINE with twice the same point)
PROJ_ONE_POINT = 1
PROJ_ALONG_LINE = 2
PROJ_AVERAGE_SPECTRUM = 3

class StaticSpectrumStream(StaticStream):
    """
    A Spectrum stream which displays only one static image/data.
    The main difference from the normal streams is that the data is 3D (a cube)
    The metadata should have a MD_WL_POLYNOMIAL
    Note that the data received should be of the (numpy) shape CYX. (where YX might be missing)
    When saving, the data will be converted to CTZYX (where TZ is 11)
    """
    def __init__(self, name, image):
        # Spectrum stream has in addition to normal stream:
        #  * projection type (1-point, line, avg. spectrum)
        #  * information about the current bandwidth displayed (avg. spectrum)
        #  * coordinates of 1st point (1-point, line)
        #  * coordinates of 2nd point (line)

        # default to showing all the data
        if isinstance(image, InstrumentalImage):
            minb, maxb = 0, 1 # unknown/unused
        else: # raw data
            assert len(image.shape) == 3
            pn = image.metadata[MD_WL_POLYNOMIAL]
            minb = polynomial.polyval(0, pn)
            maxb = polynomial.polyval(image.shape[0]-1, pn)

        # TODO: get rid of this, if not necessary
#        self.bandwidth = model.BandwidthVA((minb, maxb),
#                                           range=((minb, minb), (maxb, maxb)),
#                                           unit="m")
#

        # VAs: center wavelength + bandwidth (=center + width)
        # they might represent wavelength out of the possible values, but they
        # will automatically be clipped to fine values
        self.centerWavelength = model.FloatContinuous((maxb + minb) / 2,
                                                      range=(minb, maxb),
                                                      unit="m")
        max_bw = maxb - minb
        self.bandwidth = model.FloatContinuous(max_bw / 12,
                                               range=(max_bw/200, max_bw),
                                               unit="m")
        # TODO: how to export the average spectrum of the whole image (for the
        # bandwidth selector)? a separate method?

        # TODO: min/max: tl and br points of the image in physical coordinates
        # TODO: also need the size of a point (and density?)
#        self.point1 = model.ResolutionVA(unit="m") # FIXME: float
#        self.point2 = model.ResolutionVA(unit="m") # FIXME: float


        self.projection = model.IntEnumerated(PROJ_AVERAGE_SPECTRUM,
          choices=set([PROJ_ONE_POINT, PROJ_ALONG_LINE, PROJ_AVERAGE_SPECTRUM]))

        # this will call _updateImage(), which needs bandwidth
        StaticStream.__init__(self, name, image)

        # TODO: to convert to final raw data: raw = raw[:,numpy.newaxis,numpy.newaxis,:,:]

    def _get_bandwith_in_pixel(self):
        """
        Return the current bandwidth in pixels index
        returns (2-tuple of int): low and high pixel coordinates
        """
        center = self.centerWavelength.value
        width = self.bandwidth.value
        low = center - width / 2
        high = center + width / 2
        # no need to clip, because searchsorted will do it anyway

        # In theory it's a very complex question because you need to find the
        # solution for the polynomial at the bandwidth borders. In reality, the
        # world constraints help a lot: the polynomial is monotonic in the range
        # observed. In addition, the degree of the polynomial is very small (<5).
        # Finally, we know we are interested only by an integer solution.
        # So an easy way is to just compute the polynomial for each pixel on the
        # spectrum axis and take the closest ones (with the adapted rounding).
        data = self.raw[0]
        pn = polynomial.Polynomial(data.metadata[MD_WL_POLYNOMIAL],
                                   domain=[0, data.shape[0]-1])
        n, px_values = pn.linspace(data.shape[0]) # TODO: cache it, as the polynomial is rarely updated!

        low_px = numpy.searchsorted(px_values, low, side="left")
        if high == low:
            high_px = low_px
        else:
            high_px = numpy.searchsorted(px_values, high, side="right")

        assert low_px <= high_px
        return low_px, high_px

    def _updateImage(self):
        """ Recomputes the image with all the raw data available
          Note: for spectrum-based data, it mostly computes a projection of the
          3D data to a 2D array. The type of projection used depends on
          self.projection.
        """
        # FIXME: check that this API makes sense (projection...)

        data = self.raw[0]
        if self.projection.value == PROJ_AVERAGE_SPECTRUM:
            if self.auto_bc.value:
                # FIXME: need to fix the brightness/contrast to the min/max of
                # the _entire_ image (not just the current slice)
                # b, c = util.img.FindOptimalBC(self.raw[0], self._depth)
                brightness = None
                contrast = None
            else:
                brightness = self.brightness.value / 100
                contrast = self.contrast.value / 100

            # pick only the data inside the bandwidth
            spec_range = self._get_bandwith_in_pixel()
            # TODO: use better intermediary type if possible?, cf semcomedi
            av_data = numpy.mean(data[spec_range[0]:spec_range[1]], axis=0)

            im = util.img.DataArray2wxImage(av_data,
                                            self._depth,
                                            brightness,
                                            contrast)

            im.InitAlpha() # it's a different buffer so useless to do it in numpy

            try:
                pos = data.metadata[MD_POS]
            except KeyError:
                logging.warning("Position of image unknown")
                pos = (0, 0)

            try:
                mpp = data.metadata[MD_PIXEL_SIZE][0]
            except KeyError:
                logging.warning("pixel density of image unknown")
                # Hopefully it'll be within the same magnitude
                mpp = data.metadata[MD_SENSOR_PIXEL_SIZE][0] / 10

            self.image.value = InstrumentalImage(im, mpp, pos)
        else:
            raise NotImplementedError("Need to handle other projection types")


class StreamTree(object):
    """ Object which contains a set of streams, and how they are merged to
    appear as one image. It's a tree which has one stream per leaf and one merge
    operation per node. => recursive structure (= A tree is just a node with
    a merge method and a list of subnodes, either streamtree as well, or stream)
    """

    def __init__(self, operator=None, streams=None, **kwargs):
        """
        :param operator: (callable) a function that takes a list of
            InstrumentalImage in the same order as the streams are given and the
            additional arguments and returns one InstrumentalImage.
            By default operator is an average function.
        :param streams: (list of Streams or StreamTree): a list of streams, or
            StreamTrees.
            If a StreamTree is provided, its outlook is first computed and then
            passed as an InstrumentalImage.
        :param kwargs: any argument to be given to the operator function
        """
        self.operator = operator or util.img.Average

        streams = streams or []
        assert(isinstance(streams, list))
        for s in streams:
            assert(isinstance(s, (Stream, StreamTree)))
        self.streams = streams

        self.kwargs = kwargs


    def getStreams(self):
        """
        Return the set of streams used to compose the picture. IOW, the leaves
        of the tree.
        """
        leaves = set()
        for s in self.streams:
            if isinstance(s, Stream):
                leaves.add(s)
            elif isinstance(s, StreamTree):
                leaves |= s.getStreams()

        return leaves

    def getImage(self, rect, mpp):
        """
        Returns an InstrumentalImage composed of all the current stream images.
        Precisely, it returns the output of a call to operator.
        rect (2-tuple of 2-tuple of float): top-left and bottom-right points in
          world position (m) of the area to draw
        mpp (0<float): density (meter/pixel) of the image to compute
        """
        # TODO: probably not so useful function, need to see what canvas
        #  it will likely need as argument a wx.Bitmap, and view rectangle
        #  that will define where to save the result

        # TODO: cache with the given rect and mpp and last update time of each image

        # create the arguments list for operator
        images = []
        for s in self.streams:
            if isinstance(s, Stream):
                images.append(s.image.value)
            elif isinstance(s, StreamTree):
                images.append(s.getImage(rect, mpp))


        return self.operator(images, rect, mpp, **self.kwargs)

    def getRawImages(self):
        """
        Returns a list of all the raw images used to create the final image
        """
        # TODO not sure if a list is enough, we might need to return more
        # information about how the image was built (operator, args...)
        lraw = []
        for s in self.getStreams():
            lraw.extend(s.raw)

        return lraw
