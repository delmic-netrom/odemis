# -*- coding: utf-8 -*-
"""
Created on 16 Jul 2014

@author: Kimon Tsitsikas

Copyright © 2013-2014 Kimon Tsitsikas, Delmic

This file is part of Odemis.

Odemis is free software: you can redistribute it and/or modify it under the
terms  of the GNU General Public License version 2 as published by the Free
Software  Foundation.

Odemis is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY;  without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR  PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
Odemis. If not, see http://www.gnu.org/licenses/.
"""

from __future__ import division

from concurrent.futures._base import CancelledError, CANCELLED, FINISHED, \
    RUNNING
import cv2
import logging
import math
import numpy
from odemis import model
from odemis.acq._futures import executeTask
from odemis.dataio import hdf5
import threading
import time


# from .autofocus import AutoFocus, FINE_SPOTMODE_ACCURACY
# from . import AlignSpot, BEAM_SHIFT
def _DoUpdateConversion(future, ccd, detector, escan, sem_stage, opt_stage, 
                        focus, combined_stage):
    """
    First calls the HoleDetection to find the hole centers. Then if the current 
    sample holder is inserted for the first time, calls AlignAndOffset, 
    RotationAndScaling and enters the data to the calibration file. Otherwise 
    calls only RotationAndScaling if the sample holder is in the calibration 
    file but the hole coordinates differ from the ones in the calibration file. 
    Finally it updates the conversion metadata of the Combined Stage.
    future (model.ProgressiveFuture): Progressive future provided by the wrapper
    ccd (model.DigitalCamera): The ccd
    detector (model.Detector): The se-detector
    escan (model.Emitter): The e-beam scanner
    sem_stage (model.Actuator): The SEM stage
    opt_stage (model.Actuator): The objective stage
    focus (model.Actuator): Focus of objective lens
    combined_stage (model.Actuator): The combined stage
    returns (tuple of floats): offset #m,m
            (float): rotation #radians
            (tuple of floats): scaling
    raises:    
            CancelledError() if cancelled
            IOError
    """
    logging.debug("Starting calibration procedure...")
    try:
        if future._conversion_update_state == CANCELLED:
            raise CancelledError()

        # Detect the holes/markers of the sample holder
        logging.debug("Detect the holes/markers of the sample holder...")
        future._hole_detectionf = HoleDetection(detector, escan, sem_stage)
        first_hole, second_hole = future._hole_detectionf.result()

        # Check if the sample holder is inserted for the first time
        if True:
            logging.debug("Initial calibration to align and calculate the offset...")
            future._align_offsetf = AlignAndOffset(ccd, escan, sem_stage,
                                                   opt_stage, focus, first_hole,
                                                   second_hole)
            offset = future._align_offsetf.result()
            logging.debug("Calculate rotation and scaling...")
            future._rotation_scalingf = RotationAndScaling(ccd, escan, sem_stage,
                                                           opt_stage, focus, offset)
            rotation, scaling = future._rotation_scalingf.result()
            # Fill id, first_hole, second_hole, offset, rotation, scaling to
            # configuration file
        elif True:
            #Get offset
            logging.debug("Calculate rotation and scaling...")
            future._rotation_scalingf = RotationAndScaling(ccd, escan, sem_stage,
                                                           opt_stage, focus, offset)
            rotation, scaling = future._rotation_scalingf.result()
        else:
            #Get offset, rotation, scaling
            pass
            
        #Update combined stage conversion metadata
        logging.debug("Update combined stage conversion metadata...")
        combined_stage.updateMetadata({model.MD_ROTATION_COR: rotation})
        combined_stage.updateMetadata({model.MD_POS_COR: offset})
        combined_stage.updateMetadata({model.MD_PIXEL_SIZE_COR: scaling})

    finally:
        with future._conversion_lock:
            future._done.set()
            if future._conversion_update_state == CANCELLED:
                raise CancelledError()
            future._conversion_update_state = FINISHED

def _CancelUpdateConversion(future):
    """
    Canceller of _DoUpdateConversion task.
    """
    logging.debug("Cancelling conversion update...")

    with future._conversion_lock:
        if future._conversion_update_state == FINISHED:
            return False
        future._conversion_update_state = CANCELLED
        future._hole_detectionf.cancel()
        future._align_offsetf.cancel()
        future._rotation_scalingf.cancel()
        logging.debug("Conversion update cancelled.")

    # Do not return until we are really done (modulo 10 seconds timeout)
    future._done.wait(10)
    return True

def estimateConversionTime():
    """
    Estimates conversion procedure duration
    returns (float):  process estimated time #s
    """
    pass

def AlignAndOffset(ccd, escan, sem_stage, opt_stage, focus, first_hole,
                   second_hole):
    """
    Wrapper for DoAlignAndOffset. It provides the ability to check the progress 
    of the procedure.
    ccd (model.DigitalCamera): The ccd
    escan (model.Emitter): The e-beam scanner
    sem_stage (model.Actuator): The SEM stage
    opt_stage (model.Actuator): The objective stage
    focus (model.Actuator): Focus of objective lens
    first_hole (tuple of floats): Coordinates of first hole
    second_hole (tuple of floats): Coordinates of second hole
    returns (ProgressiveFuture): Progress DoAlignAndOffset
    """
    # Create ProgressiveFuture and update its state to RUNNING
    est_start = time.time() + 0.1
    f = model.ProgressiveFuture(start=est_start,
                                end=est_start + estimateOffsetTime())
    f._align_offset_state = RUNNING

    # Task to run
    f.task_canceller = _CancelAlignAndOffset
    f._offset_lock = threading.Lock()

    # Create autofocus and centerspot module
    f._alignspotf = model.InstantaneousFuture()

    # Run in separate thread
    offset_thread = threading.Thread(target=executeTask,
                  name="Align and offset",
                  args=(f, _DoAlignAndOffset, f, ccd, escan, sem_stage, opt_stage,
                        focus, first_hole, second_hole))

    offset_thread.start()
    return f

def _DoAlignAndOffset(future, ccd, escan, sem_stage, opt_stage, focus,
                      first_hole, second_hole):
    """
    Performs referencing of both stages. Write one CL spot and align it, 
    moving both SEM stage and e-beam (spot alignment). Calculate the offset 
    based on the final position plus the offset of the hole from the expected 
    position.
    future (model.ProgressiveFuture): Progressive future provided by the wrapper
    ccd (model.DigitalCamera): The ccd
    escan (model.Emitter): The e-beam scanner
    sem_stage (model.Actuator): The SEM stage
    opt_stage (model.Actuator): The objective stage
    focus (model.Actuator): Focus of objective lens
    first_hole (tuple of floats): Coordinates of first hole
    second_hole (tuple of floats): Coordinates of second hole
    returns (tuple of floats): offset #m,m
    raises:    
        CancelledError() if cancelled
        IOError if CL spot not found
    """
    logging.debug("Starting alignment and offset calculation...")
    try:
        if future._align_offset_state == CANCELLED:
            raise CancelledError()

        # Spot alignment using the beam shift
#         future._alignspotf = AlignSpot(ccd, opt_stage, escan, focus, BEAM_SHIFT)
#         dist = future._alignspotf.result()

    finally:
        with future._offset_lock:
            if future._align_offset_state == CANCELLED:
                raise CancelledError()
            future._align_offset_state = FINISHED

def _CancelAlignAndOffset(future):
    """
    Canceller of _DoAlignAndOffset task.
    """
    logging.debug("Cancelling align and offset calculation...")

    with future._offset_lock:
        if future._align_offset_state == FINISHED:
            return False
        future._align_offset_state = CANCELLED
        future._alignspotf.cancel()
        logging.debug("Align and offset calculation cancelled.")

    return True

def estimateOffsetTime():
    """
    Estimates alignment and offset calculation procedure duration
    returns (float):  process estimated time #s
    """
    pass

def RotationAndScaling(ccd, escan, sem_stage, opt_stage, focus, offset):
    """
    Wrapper for DoRotationAndScaling. It provides the ability to check the 
    progress of the procedure.
    ccd (model.DigitalCamera): The ccd
    escan (model.Emitter): The e-beam scanner
    sem_stage (model.Actuator): The SEM stage
    opt_stage (model.Actuator): The objective stage
    focus (model.Actuator): Focus of objective lens
    offset (tuple of floats): #m,m
    returns (ProgressiveFuture): Progress DoRotationAndScaling
    """
    # Create ProgressiveFuture and update its state to RUNNING
    est_start = time.time() + 0.1
    f = model.ProgressiveFuture(start=est_start,
                                end=est_start + estimateRotationAndScalingTime())
    f._rotation_scaling_state = RUNNING

    # Task to run
    f.task_canceller = _CancelRotationAndScaling
    f._rotation_lock = threading.Lock()

    # Run in separate thread
    rotation_thread = threading.Thread(target=executeTask,
                  name="Rotation and scaling",
                  args=(f, _DoRotationAndScaling, f, ccd, escan, sem_stage, opt_stage,
                        focus, offset))

    rotation_thread.start()
    return f

def _DoRotationAndScaling(future, ccd, escan, sem_stage, opt_stage, focus,
                          offset):
    """
    Move the stages to four diametrically opposite positions in order to 
    calculate the rotation and scaling.
    future (model.ProgressiveFuture): Progressive future provided by the wrapper
    ccd (model.DigitalCamera): The ccd
    escan (model.Emitter): The e-beam scanner
    sem_stage (model.Actuator): The SEM stage
    opt_stage (model.Actuator): The objective stage
    focus (model.Actuator): Focus of objective lens
    offset (tuple of floats): #m,m
    returns (float): rotation #radians
            (tuple of floats): scaling
    raises:    
        CancelledError() if cancelled
        IOError if CL spot not found
    """
    logging.debug("Starting rotation and scaling calculation...")
    try:
        if future._rotation_scaling_state == CANCELLED:
            raise CancelledError()

    finally:
        with future._rotation_lock:
            if future._rotation_scaling_state == CANCELLED:
                raise CancelledError()
            future._rotation_scaling_state = FINISHED

def _CancelRotationAndScaling(future):
    """
    Canceller of _DoRotationAndScaling task.
    """
    logging.debug("Cancelling rotation and scaling calculation...")

    with future._rotation_lock:
        if future._rotation_scaling_state == FINISHED:
            return False
        future._rotation_scaling_state = CANCELLED
        logging.debug("Rotation and scaling calculation cancelled.")

    return True

def estimateRotationAndScalingTime():
    """
    Estimates rotation and scaling calculation procedure duration
    returns (float):  process estimated time #s
    """
    pass

def HoleDetection(detector, escan, sem_stage):
    """
    Wrapper for DoHoleDetection. It provides the ability to check the 
    progress of the procedure.
    detector (model.Detector): The se-detector
    escan (model.Emitter): The e-beam scanner
    sem_stage (model.Actuator): The SEM stage
    returns (ProgressiveFuture): Progress DoHoleDetection
    """
    # Create ProgressiveFuture and update its state to RUNNING
    est_start = time.time() + 0.1
    f = model.ProgressiveFuture(start=est_start,
                                end=est_start + estimateHoleDetectionTime())
    f._hole_detection_state = RUNNING

    # Task to run
    f.task_canceller = _CancelHoleDetection
    f._detection_lock = threading.Lock()

    # Run in separate thread
    detection_thread = threading.Thread(target=executeTask,
                  name="Hole detection",
                  args=(f, _DoHoleDetection, f, detector, escan, sem_stage))

    detection_thread.start()
    return f

def _DoHoleDetection(future, detector, escan, sem_stage):
    """
    Detects the centers of the holes on the sample holder.
    future (model.ProgressiveFuture): Progressive future provided by the wrapper
    detector (model.Detector): The se-detector
    escan (model.Emitter): The e-beam scanner
    sem_stage (model.Actuator): The SEM stage
    returns (tuple of floats): first_hole #m,m 
            (tuple of floats): second_hole #m,m
    raises:    
        CancelledError() if cancelled
        IOError if holes not found
    """
    logging.debug("Starting hole detection...")
    try:
        if future._hole_detection_state == CANCELLED:
            raise CancelledError()
        
    finally:
        with future._detection_lock:
            if future._hole_detection_state == CANCELLED:
                raise CancelledError()
            future._hole_detection_state = FINISHED

def _CancelHoleDetection(future):
    """
    Canceller of _DoHoleDetection task.
    """
    logging.debug("Cancelling hole detection...")

    with future._detection_lock:
        if future._hole_detection_state == FINISHED:
            return False
        future._hole_detection_state = CANCELLED
        logging.debug("Hole detection cancelled.")

    return True

def estimateHoleDetectionTime():
    """
    Estimates hole detection procedure duration
    returns (float):  process estimated time #s
    """
    pass

def FindHoleCenter(image):
    """
    Detects the center of a hole contained in SEM image.
    image (model.DataArray): SEM image
    returns (tuple of floats): Coordinates of hole
    raises:    
        IOError if hole not found
    """
    contours, hierarchy = cv2.findContours(image, cv2.RETR_LIST , cv2.CHAIN_APPROX_SIMPLE)
    if contours == []:
        raise IOError("Hole not found.")

    area = 0
    whole_area = numpy.prod(image.shape)
    for cnt in contours:
        new_area = cv2.contourArea(cnt)
        #Make sure you dont detect the whole image frame or just a spot
        if new_area > area and new_area < 0.8 * whole_area and new_area > 0.01 * whole_area:
            area = new_area
            max_cnt = cnt

    # cv2.drawContours(image, [max_cnt], 0, 255, 2)
    # Find center of hole
    center_x = numpy.mean([min(max_cnt[:, :, 0]), max(max_cnt[:, :, 0])])
    center_y = numpy.mean([min(max_cnt[:, :, 1]), max(max_cnt[:, :, 1])])
    # image[center_x, center_y] = 255

    # cv2.imshow('im', image)
    # cv2.waitKey()
    return (center_x, center_y)
