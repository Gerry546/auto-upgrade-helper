#!/usr/bin/env python
# SPDX-License-Identifier: GPL-2.0-or-later
# vim: set ts=4 sw=4 et:
#
# Copyright (c) 2015 Intel Corporation
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#

import os
import logging as log
from logging import debug as D
from logging import info as I
from logging import warning as W
from logging import error as E
from logging import critical as C
import sys

from errors import *
from utils.git import Git
from utils.bitbake import *

class BuildHistory(object):
    def __init__(self, bb, pn, workdir):
        self.bb = bb
        self.pn = pn
        self.workdir = workdir

    def init(self, machines):
        for machine in machines:
            try:
                self.bb.complete(self.pn, machine)
            except Error as e:
                for line in e.stdout.split("\n") + e.stderr.split("\n"):
                    # version going backwards is not a real error
                    if re.match(".* went backwards which would break package feeds .*", line):
                        break
                else:
                    raise e


    def diff(self):
        try:
            cmd = "buildhistory-diff"
            stdout, stderr = bb.process.run(cmd)
            if stdout and os.path.exists(self.workdir):
                with open(os.path.join(self.workdir, "buildhistory-diff.txt"),
                        "w+") as log:
                    log.write(stdout)

            cmd_full = "buildhistory-diff -a"
            stdout, stderr = bb.process.run(cmd_full)
            if stdout and os.path.exists(self.workdir):
                with open(os.path.join(self.workdir, "buildhistory-diff-full.txt"),
                        "w+") as log:
                    log.write(stdout)
        except bb.process.ExecutionError as e:
            W( "%s: Buildhistory checking fails\n%s" % (self.pn, e.stdout))
