# -*- coding: utf-8 -*-
'''
Created on 19 Jul 2017

@author: Éric Piel, Philip Winkler

Copyright © 2017 Éric Piel, Delmic

This file is part of Odemis.

Odemis is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License version 2 as published by the Free Software Foundation.

Odemis is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with Odemis. If not, see http://www.gnu.org/licenses/.
'''

# This is a series of classes which use different methods to compute the "best
# location" of an image set based on their metadata and content. IOW, it does
# "image registration".


from __future__ import division
from odemis.acq.drift import MeasureShift
import numpy
import math
from odemis import model
import logging

BEST_MATCH = 0.9  # minimum match value indicating optimal shift value
GOOD_MATCH = 0.2  # minimum match value indicating shift value can be used in the average position calculation
# maximum percentage of overlap size indicating an extreme shift value that
# should be aborted
EXTREME_SHIFT = 0.6

LEFT = 1  # direction in pos_to_left_right function
RIGHT = -1


class IdentityRegistrar(object):
    """ Returns position as-is """

    def __init__(self):
        self.tile_pos = []
        self.dep_tiles_pos = []

    def addTile(self, tile, dependent_tiles=None):
        """
        Extends grid by one tile.
        tile (DataArray of shape YX): each image must have at least MD_POS and MD_PIXEL_SIZE metadata. 
        They should all have the same dtype.
        dependent_tiles (list of DataArray or None): each of the dependent tile, where their position 
        can be considered fixed relative to the main tile. Their content and metadata are not used
        for the computation of the final position.
        """
        self.tile_pos.append(tile.metadata[model.MD_POS])
        if dependent_tiles:
            pos = [t.metadata[model.MD_POS] for t in dependent_tiles]
            self.dep_tiles_pos.append(pos)

    def getPositions(self):
        """
        returns:
        tile_positions (list of N tuples of 2 floats)): the adjusted position in X/Y for each tile, in the order they were added
        dep_tile_positions (list of N tuples of tuples of 2 floats): the adjusted position for each dependent tile 
        (in the order they were passed)
        """
        return self.tile_pos, self.dep_tiles_pos


class ShiftRegistrar(object):
    """
    Locates the position of the image relative to the previous top tiles (horizontally and vertically) 
    by using cross-correlation. The cross-correlation is done using just the part of the images which are 
    supposed to be overlapping. In case the cross-correlation doesn't work (based on a couple of simple tests), 
    fallback to the average shift on the same axis.
    """

    def __init__(self):
        # arrays to store the vertical/horizontal shift values measured for
        # each tile
        # initialize grid to 1x1. The size will increase as new tiles are
        # added.
        self.nx = 1
        self.ny = 1
        self.coords_ver = [[None]]
        self.coords_hor = [[None]]
        self.shifts = [[None]]
        self.tiles = [[None]]
        self.last_ver = (0, 0)  # last vertical shift measured
        self.last_hor = (0, 0)  # last horizontal shift measured

        # Initialize overlap. This will be modified after the second tile has been added.
        # A value is needed to avoid errors when calculating the position for
        # the first tile.
        self.ovrlp = 0

        # List of 2D indices for grid positions in order of acquisition
        self.acqOrder = []

        self.shift_tile_dep_tiles = []  # N x K list. N: number of tiles, K: number of dep_tiles.
        # Shift between main tile and dependent tiles

        self.px_size = None  # Tuple of 2 ints. (X,Y) pixel size of the current tile in m/px.
        self.size = None  # Tuple of 2 ints. (Y,X) shape of the current tile in px.
        self.posX = None  # int. Position of the current tile in the grid. (0,0) is the top left, posX
        # increases when moving to the right
        self.posY = None  # int. Y position, increases when moving down.
        self.pos_prev_x = None  # int. X coordinate of previous tile. Used to determine whether
        # the current tile should be compared to the right or to the left tile.
        self.osize = None  # int. Overlap size in pixels
        self.tsize = None  # int. Expected shift in pixels, distance between the centers of two tiles

    def addTile(self, tile, dependent_tiles=None):
        """
        Extends grid by one tile.
        tile (DataArray of shape YX): each image must have at least MD_POS and MD_PIXEL_SIZE metadata. 
        They should all have the same dtype.
        dependent_tiles (list of K DataArray or None): each of the dependent tile, where their position 
        can be considered fixed relative to the main tile. Their content and metadata are not used
        for the computation of the final position.
        Not every random order of adding tiles is supported: the first tile has to be in the left top 
        position, any following tile must either be inserted to the right of an existing tile, to its left,
        or to the bottom. The grid has to be filled up from top to bottom, moving from the bottom up is not 
        supported.
        """

        if dependent_tiles is None:
            dependent_tiles = []
        else:
            # Shift between tile and its dependent tiles
            self.shift_tile_dep_tiles.append([])

        # Find position of the tile in the grid. Indices of grid position are
        # given as posX, posY.
        if self.tiles[0][0] is None:
            self.size = tile.shape
            self.px_size = tile.metadata[model.MD_PIXEL_SIZE]
            self.posX = 0
            self.posY = 0

            self.pos_prev_x = 0  # used to determine if tile should be compared to right or left tile
        else:
            if tile.shape != self.tiles[0][0].shape:
                raise ValueError("Tile shape differs from previous tile shapes %s != %s" %
                                 (tile.shape, self.tiles[0][0].shape))

            md_pos = tile.metadata[model.MD_POS]

            # Find the registered tile that is closest to the new tile.
            pos_prev, md_pos_prev = self._find_closest_tile(md_pos)

            # Insert new tile either to the right or to the bottom of the
            # closest tile.
            ver_diff = md_pos[1] - md_pos_prev[1]
            hor_diff = md_pos[0] - md_pos_prev[0]
            if abs(ver_diff) > abs(hor_diff):
                if ver_diff < 0:
                    self.posY = pos_prev[0] + 1
                    self.posX = pos_prev[1]
                    if len(self.shifts) <= self.posY:
                        self._updateGrid("y")  # extend grid in y direction
                else:
                    self.posY = pos_prev[0] - 1
                    self.posX = pos_prev[1]
            else:
                if hor_diff > 0:
                    self.posY = pos_prev[0]
                    self.posX = pos_prev[1] + 1
                    if len(self.shifts[0]) <= self.posX:
                        self._updateGrid("x")  # extend grid in x direction
                else:
                    self.posY = pos_prev[0]
                    self.posX = pos_prev[1] - 1

            self.pos_prev_x = pos_prev[1]
            # Calculate overlap
            if abs(ver_diff) > abs(hor_diff):
                size_meter = self.size[0] * self.px_size[1]
                diff = abs(tile.metadata[model.MD_POS][1] - md_pos_prev[1])
                self.ovrlp = abs(size_meter - diff) / size_meter
                # self.size is given as YX, MD_POS as XY
                self.osize = self.size[0] * \
                    self.ovrlp  # overlap size in pixels
                self.tsize = int(self.size[0] - self.osize)  # expected shift, distance between
                # the centers of two tiles
            else:
                size_meter = self.size[1] * self.px_size[0]
                diff = abs(tile.metadata[model.MD_POS][0] - md_pos_prev[0])
                self.ovrlp = abs(size_meter - diff) / size_meter

                self.osize = self.size[1] * \
                    self.ovrlp  # overlap size in pixels
                self.tsize = int(self.size[1] - self.osize)

        for dt in dependent_tiles:
            sdt = numpy.subtract(dt.metadata[model.MD_POS], tile.metadata[model.MD_POS])
            self.shift_tile_dep_tiles[-1].append(sdt)

        self._compute_registration(tile, self.posY, self.posX)

    def getPositions(self):
        """
        returns:
        tile_positions (list of N tuples): the adjusted position in X/Y for each tile, in the order they were added
        dep_tile_positions (list of N tuples of K tuples of 2 floats): for each tile, it returns 
        the adjusted position of each dependent tile (in the order they were passed)
        """
        firstPosition = numpy.divide(
            self.tiles[0][0].metadata[model.MD_POS], self.px_size)
        tile_positions = []
        dep_tile_positions = []

        for ti in self.acqOrder:
            shift = self.shifts[ti[0]][ti[1]]
            tile_positions.append(((shift[0] + firstPosition[0]) * self.px_size[0],
                                   (firstPosition[1] - shift[1]) * self.px_size[1]))

        # Return positions for dependent tiles
        for t, sdts in zip(tile_positions, self.shift_tile_dep_tiles):
            dts = []  # dependent tiles for tile
            for sdt in sdts:
                dts.append((t[0] + sdt[0], t[1] + sdt[1]))
            dep_tile_positions.append(dts)

        return tile_positions, dep_tile_positions

    def _find_closest_tile(self, pos):
        """ finds the tile in the grid that is closest to pos.
        returns: 
        pos_prev: tuple of two ints. Grid position of closest tile.
        md_pos_prev: actual position of closest tile in m """
        minDist = float("inf")
        for i in range(len(self.tiles)):
            for j in range(len(self.tiles[0])):
                if self.tiles[i][j] is not None:
                    md_pos_ij = self.tiles[i][j].metadata[model.MD_POS]
                    dist = math.hypot(pos[0] - md_pos_ij[0], pos[1] - md_pos_ij[1])
                    if dist < minDist:
                        minDist = dist
                        pos_prev = (i, j)
                        md_pos_prev = self.tiles[i][j].metadata[model.MD_POS]
        return pos_prev, md_pos_prev

    def _updateGrid(self, direction):
        """ extends grid by one row (direction = "y") or one column (direction = "x") """
        if direction == "x":
            self.nx += 1
            for i in range(len(self.tiles)):
                self.tiles[i].append(None)
                self.coords_ver[i].append(None)
                self.coords_hor[i].append(None)
                self.shifts[i].append(None)
        else:
            self.tiles.append([None] * self.nx)
            self.coords_ver.append([None] * self.nx)
            self.coords_hor.append([None] * self.nx)
            self.shifts.append([None] * self.nx)

    def _estimateROI(self, shift):
        """
        Given a shift vector between two tiles, it returns the corresponding
        roi's that overlap.
        shift (2 ints): shift on the roi
        return (2 tuples of 4 ints): left, top, right, bottom pixels in each tile
        """
        if (shift[0] >= self.size[1]) or (shift[1] >= self.size[0]):
            raise ValueError(
                "There is no overlap between tiles for the shift given %s", shift)

        # different sizes when shift is negative
        # reference image
        l1 = max(0, min(self.size[1], shift[0]))
        t1 = max(0, min(self.size[0], shift[1]))
        r1 = max(0, min(self.size[1], shift[0] + self.size[1]))
        b1 = max(0, min(self.size[0], shift[1] + self.size[0]))

        # shifted image
        l2 = max(0, min(self.size[1], - shift[0]))
        t2 = max(0, min(self.size[0], - shift[1]))
        r2 = max(0, min(self.size[1], self.size[1] - shift[0]))
        b2 = max(0, min(self.size[0], self.size[0] - shift[1]))

        return (l1, t1, r1, b1), (l2, t2, r2, b2)

    def _estimateMatch(self, imageA, imageB, shift=(0, 0)):
        """
        Returns an estimation of the similarity between the given images
        when the second is shifted by the shift value. It is used to assess 
        the quality of a shift measurement by giving the shifted image.
        return (0 <= float<=1): the bigger, the more similar are the images
        """
        # If case the shift is extreme, force the match to 0, to indicate
        # something is wrong
        min_shift = math.sqrt(2) * (self.tsize - self.osize) - self.osize * EXTREME_SHIFT
        max_shift = math.sqrt(2) * (self.tsize - self.osize) + self.osize * EXTREME_SHIFT
        if not min_shift <= math.hypot(*shift) <= max_shift:
            return 0

        (l1, t1, r1, b1), (l2, t2, r2, b2) = self._estimateROI(shift)

        imageA_sh = numpy.array(imageA)[t1:b1, l1:r1]
        imageB_sh = numpy.array(imageB)[t2:b2, l2:r2]

        avg = (numpy.sum(imageA_sh) / imageA_sh.size,
               numpy.sum(imageB_sh) / imageB_sh.size)

        dist = (numpy.subtract(imageA_sh, avg[0]),
                numpy.subtract(imageB_sh, avg[1]))

        covar = numpy.sum(dist[0] * dist[1]) / imageA_sh.size

        var = (numpy.sum(numpy.power(dist[0], 2)) / imageA_sh.size,
               numpy.sum(numpy.power(dist[1], 2)) / imageB_sh.size)

        stDev = (math.sqrt(var[0]), math.sqrt(var[1]))

        if stDev[0] == 0 or stDev[1] == 0:
            return 0

        return covar / (stDev[0] * stDev[1])

    def _get_shift(self, prev_tile, tile, shift=(0, 0)):
        """
        Measures the shift on the overlap between the two tiles when the second is shifted \
        by the shift value.
        shift (2 ints): shift between prev_tile and tile
        return (2 ints): guessed shift
        """
        (l1, t1, r1, b1), (l2, t2, r2, b2) = self._estimateROI(shift)

        a = prev_tile[t1:b1, l1:r1]
        b = tile[t2:b2, l2:r2]
        # TODO: Check if shift is calculated properly. It might be the case that
        # very small overlap areas that result in a good match are favoured over the correct
        # bigger overlap area.
        [x, y] = MeasureShift(b, a)
        return x, y

    def _mean_shift(self, row, col, coords_array):
        """
        Returns the mean shift computed along the given row and column
        """
        val = [coords_array[row][i] for i in range(1, col) if coords_array[row][i] is not None] + \
              [coords_array[i][col]
                  for i in range(1, row) if coords_array[i][col] is not None]
        if not val:
            raise ValueError("Not enough data to compute mean horizontal shift")
        mean_x = int(sum(v[0] for v in val) / len(val))
        mean_y = int(sum(v[1] for v in val) / len(val))
        return mean_x, mean_y

    def _pos_to_left_right(self, row, col, xdir):
        """
        Returns the position of the new tile after calculating the shift with the
        neighbor on the left or right
        xdir: LEFT, RIGHT
        """
        # shift compared to left
        x, y = 0, 0

        # calculate the shift compared to the neighbor on the left if possible
        pos = None
        match = 0

        tile = self.tiles[row][col]
        # the expected shift vector between the two tiles if the scanning would
        # be ideal
        exp_shift = (self.tsize, 0)

        if (xdir == LEFT and col > 0) or (xdir == RIGHT and col < self.nx):
            if xdir == LEFT:
                prev_pos = self.shifts[row][col - 1]
                prev_tile = self.tiles[row][col - 1]
                x, y = self._get_shift(prev_tile, tile, exp_shift)
            elif xdir == RIGHT:
                prev_pos = self.shifts[row][col + 1]
                prev_tile = self.tiles[row][col + 1]
                x, y = self._get_shift(tile, prev_tile, exp_shift)
                y = -y
                x = -x
            match = self._estimateMatch(
                prev_tile, tile, (exp_shift[0] - x, exp_shift[1] - y))

            if match < BEST_MATCH and (row > 1 or col > 1):
                # if the shift calculated does not give a sufficient match,
                # try the horizontal mean shift along this row and column if
                # possible
                try:
                    mean_x, mean_y = self._mean_shift(row, col, self.coords_hor)
                except ValueError:
                    # if a mean value is not available try the last horizontal
                    # shift measured
                    mean_x, mean_y = self.last_hor
                match_c = self._estimateMatch(prev_tile, tile,
                                              (exp_shift[0] - mean_x, exp_shift[1] - mean_y))
                if match_c > match:
                    x, y = mean_x, mean_y
                    match = match_c

                if (mean_x, mean_y) != (0, 0):
                    # try to calculate shift from here, maybe it works better
                    # now
                    drift = self._get_shift(
                        prev_tile, tile, (exp_shift[0] - mean_x, exp_shift[1] - mean_y))
                    mean_x += drift[0]
                    mean_y += drift[1]
                    match_c = self._estimateMatch(
                        prev_tile, tile, (exp_shift[0] - mean_x, exp_shift[1] - mean_y))
                    if match_c > match:
                        x, y = mean_x, mean_y
                        match = match_c

            # store the new horizontal shift computed
            self.last_hor = x, y
            if match >= BEST_MATCH:
                self.coords_hor[row][col] = x, y

            # calculate the new position based on the shift with respect to the
            # neighbour position (prev_pos)
            if xdir == LEFT:
                pos = (int(prev_pos[0] + (self.size[1] * (1 - self.ovrlp)) - x),
                       int(prev_pos[1] - y))
                if pos[0] < prev_pos[0]:
                    logging.warning("Inserted tile to the wrong side (left instead of right)")
            else:
                pos = (int(prev_pos[0] - (self.size[1] * (1 - self.ovrlp)) - x),
                       int(prev_pos[1] - y))
                if pos[0] > prev_pos[0]:
                    logging.warning("Inserted tile to the wrong side (right instead of left)")

        return pos, match

    def _pos_to_top(self, row, col):
        """
        Returns the position of the new tile after calculating the shift with the
        neighbor on the top
        """
        # shift compared to top
        x, y = 0, 0

        # calculate the shift compared to the neighbor on the top if possible
        pos = None
        match = 0

        tile = self.tiles[row][col]
        # the expected shift vector between the two tiles if the scanning would
        # be ideal
        exp_shift = (0, self.tsize)
        if row > 0:
            prev_pos = self.shifts[row - 1][col]
            prev_tile = self.tiles[row - 1][col]
            x, y = self._get_shift(prev_tile, tile, exp_shift)
            match = self._estimateMatch(
                prev_tile, tile, (exp_shift[0] - x, exp_shift[1] - y))

            if match < BEST_MATCH and (row > 1 or col > 1):
                # if the shift calculated does not give a sufficient match,
                # try the vertical mean shift along this row and column if
                # possible
                try:
                    mean_x, mean_y = self._mean_shift(
                        row, col, self.coords_ver)
                except ValueError:
                    # if a mean value is not available try the last vertical
                    # shift measured
                    mean_x, mean_y = self.last_ver
                match_c = self._estimateMatch(
                    prev_tile, tile, (exp_shift[0] - mean_x, exp_shift[1] - mean_y))
                if match_c > match:
                    x, y = mean_x, mean_y
                    match = match_c

                if (mean_x, mean_y) != (0, 0):
                    # try to calculate shift from here, maybe it works better
                    # now
                    drift = self._get_shift(
                        prev_tile, tile, (exp_shift[0] - mean_x, exp_shift[1] - mean_y))
                    mean_x += drift[0]
                    mean_y += drift[1]
                    match_c = self._estimateMatch(
                        prev_tile, tile, (exp_shift[0] - mean_x, exp_shift[1] - mean_y))
                    if match_c > match:
                        x, y = mean_x, mean_y
                        match = match_c

            # store the new vertical shift computed
            self.last_ver = x, y
            if match >= BEST_MATCH:
                self.coords_ver[row][col] = x, y

            # calculate the new position based on the shift with respect to the
            # top neighbor position (prev_pos)
            pos = (int(prev_pos[0] - x),
                   int(prev_pos[1] + (self.size[0] * (1 - self.ovrlp)) - y))

        return pos, match

    def _compute_registration(self, tile, row, col):
        """
        Stitches one tile to the overall image. Tiles should be inserted in an
        order such that the previous top or previous left tiles have already been inserted.
        tile (DataArray of shape YX): Tile to be stitched
        row (0<=int): Row of the tile position
        col (0<=int): Column of the tile position
        raise ValueError: if the top or left tile hasn't been provided yet
        """
        if (row >= 1 and self.tiles[row - 1][col] is None) and (col >= 1 and self.tiles[row][col - 1] is None):
            raise ValueError(
                "Trying to stitch image at %d,%d, while its previous image hasn't been stitched yet")
        # store the tile
        self.tiles[row][col] = tile

        # expected tile position, if there would be no shift
        # we avoid using tsize to not loose precision due to rounding
        ox = int(col * (self.size[1] * (1 - self.ovrlp)))
        oy = int(row * (self.size[0] * (1 - self.ovrlp)))

        pos = None
        pos2 = None
        match = 0
        match2 = 0

        if self.pos_prev_x < col:
            if col != 0 and self.tiles[row][col - 1] is not None:
                # calculate the shift compared to the neighbor on the left if
                # possible
                pos, match = self._pos_to_left_right(row, col, LEFT)
        elif self.pos_prev_x > col:
            if col != self.nx and self.tiles[row][col + 1] is not None:
                # calculate the shift compared to the neighbor on the right if
                # possible
                pos, match = self._pos_to_left_right(row, col, RIGHT)

        if row != 0 and self.tiles[row - 1][col] is not None:
            # calculate the shift compared to the neighbor on the top if
            # possible
            pos2, match2 = self._pos_to_top(row, col)

        # get rid of extreme values
        if (pos is None) and (pos2 is None):
            pos = (ox, oy)
        elif (pos is None):
            pos = pos2
        elif (pos2 is None):
            pass
        elif match > GOOD_MATCH and match2 > GOOD_MATCH:
            # if the match is not really bad, then take the average position
            pos = (int((pos[0] + pos2[0]) / 2), int((pos[1] + pos2[1]) / 2))
        elif match2 > match:
            # otherwise just keep the best one
            pos = pos2
        elif match2 == 0 and match == 0:
            # no good value, fall back to given position
            pos = (ox, oy)

        # store the position of the tile
        self.shifts[row][col] = pos

        self.acqOrder.append([row, col])
