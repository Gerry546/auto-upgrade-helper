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
# This module implements logic for run image tests on recipes when upgrade
# process succeed.
#

import os

from logging import info as I

from errors import Error, TestImageError

class TestImage():
    def __init__(self, devtool, uh_work_dir, opts, groups, image):
        self.devtool = devtool
        self.uh_work_dir = uh_work_dir
        self.opts = opts
        self.groups = self._get_testable_groups(groups.get('succeeded', []))
        self.image = image

        self.logdir = os.path.join(uh_work_dir, "testimage-logs")
        os.makedirs(self.logdir, exist_ok=True)

    def _has_ptest_package(self, pkg_ctx):
        packages = (pkg_ctx.get('env', {}).get('PACKAGES', '') or '').split()
        return "{}-ptest".format(pkg_ctx['PN']) in packages

    def _get_testable_groups(self, groups):
        return [group for group in groups
                if any(self._has_ptest_package(pkg_ctx) for pkg_ctx in group['pkgs'])]

    def _get_pkgs_to_install(self, groups):
        pkgs_out = []

        for g in groups:
            for c in g['pkgs']:
                if self._has_ptest_package(c):
                    pkgs_out.append(c['PN'])

        return sorted(set(pkgs_out))

    def testimage(self, groups, machine, image):
        pkgs = self._get_pkgs_to_install(groups)
        I(" Installing additional packages to the image: {}".format(" ".join(pkgs)))
        I("   running devtool test-image for %s on %s ..." % (image, machine))

        devtool_output = ""
        try:
            devtool_output = self.devtool.test_image(image, packages=pkgs, machine=machine)
        except Error as e:
            I("   running the testimage failed! Collecting logs...")
            devtool_output = (e.stdout or "") + (e.stderr or "")
            failed_log = os.path.join(self.logdir, "devtool-test-image-failed.log")
            with open(failed_log, 'w') as f:
                f.write(devtool_output)
            return TestImageError("devtool test-image failed; see {}".format(failed_log),
                                  stdout=e.stdout, stderr=e.stderr)

        if devtool_output:
            with open(os.path.join(self.logdir, "devtool-test-image.log"), 'w') as f:
                f.write(devtool_output)
        I(" All done! Testimage/ptest/qemu logs are collected to {}".format(self.logdir))
        return None

    def run(self):
        if not self.groups:
            I("  No successful upgrades with -ptest packages available for test-image; skipping.")
            return None

        machine = self.opts['machines'][0]
        I("  Testing image for %s ..." % machine)
        return self.testimage(self.groups, machine, self.image)
