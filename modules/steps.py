#!/usr/bin/env python
# SPDX-License-Identifier: GPL-2.0-or-later
# vim: set ts=4 sw=4 et:
#
# Copyright (c) 2013 - 2015 Intel Corporation
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
import shutil
import re

from logging import debug as D
from logging import info as I
from logging import warning as W

from errors import *
from buildhistory import BuildHistory

def load_env(devtool, bb, git, opts, group):
    group['workdir'] = os.path.join(group['base_dir'], group['name'])
    os.mkdir(group['workdir'])
    for pkg_ctx in group['pkgs']:
        pkg_ctx['env'] = bb.env(pkg_ctx['PN'])
        pkg_ctx['recipe_dir'] = os.path.dirname(pkg_ctx['env']['FILE'])

def buildhistory_init(devtool, bb, git, opts, group):
    if not opts['buildhistory']:
        return

    group['buildhistory'] = BuildHistory(bb, group)
    I(" %s: Initial buildhistory for %s ..." % (group['name'],
            opts['machines'][:1]))
    group['buildhistory'].init(opts['machines'][:1])

def _extract_license_diff(devtool_output):
    licenseinfo = []
    for line in devtool_output.split('\n'):
        if line.startswith("NOTE: New recipe is"):
            recipepath = line.split()[4]
            with open(recipepath, 'rb') as f:
                lines = f.readlines()

            extracting = False
            with open(recipepath, 'wb') as f:
                for line in lines:
                     if line.startswith(b'# FIXME: the LIC_FILES_CHKSUM'):
                         extracting = True
                     elif extracting == True and not line.startswith(b'#') and len(line) > 1:
                         extracting = False
                     if extracting == True:
                         licenseinfo.append(line[2:])
                     else:
                         f.write(line)
    D(" License diff extracted: {}".format(b"".join(licenseinfo).decode('utf-8')))
    return licenseinfo

def _make_commit_msg(group):
    def _get_version(p):
        if p['NPV'].endswith("new-commits-available"):
            return "to latest revision".format(p['PN'])
        else:
            return "{} -> {}".format(p['PV'], p['NPV'])

    pn = group['name']
    return "{}: upgrade {}".format(pn, ",".join([_get_version(p) for p in group['pkgs']]))

def _devtool_upgrade(devtool, bb, git, opts, pkg_ctx):
    try:
        devtool_output = devtool.upgrade(pkg_ctx['PN'], pkg_ctx['NPV'], pkg_ctx['NSRCREV'])
        D(" 'devtool upgrade' printed:\n%s" %(devtool_output))
        # If devtool failed to rebase patches, it does not fail, but we should
        if 'conflict' in devtool_output:
            raise DevtoolError("Running 'devtool upgrade' for recipe %s failed." %(pkg_ctx['PN']), devtool_output)
    except DevtoolError as e1:
        try:
            devtool_output = devtool.reset()
        except DevtoolError as e2:
            pass
        raise e1

    license_diff_info = _extract_license_diff(devtool_output)
    if len(license_diff_info) > 0:
        pkg_ctx['license_diff_fn'] = "license-diff-{}.txt".format(pkg_ctx['PV'])
        with open(os.path.join(pkg_ctx['workdir'], pkg_ctx['license_diff_fn']), 'wb') as f:
            f.write(b"".join(license_diff_info))


def devtool_upgrade(devtool, bb, git, opts, group):
    group['commit_msg'] = _make_commit_msg(group)
    for p in group['pkgs']:
        _devtool_upgrade(devtool, bb, git, opts, p)

def _compile(bb, pkg, machine, workdir):
        try:
            bb.complete(pkg, machine)
        except Error as e:
            with open("{}/bitbake-output-{}.txt".format(workdir, machine), 'w') as f:
                f.write(e.stdout + e.stderr)
            for line in e.stdout.split("\n") + e.stderr.split("\n"):
                # version going backwards is not a real error
                if re.match(".* went backwards which would break package feeds .*", line):
                    break
                # 'not in COMPATIBLE_HOST/MACHINE is not a real error
                if re.match(".*not in COMPATIBLE.*", line):
                    break
            else:
                raise CompilationError()

def compile(devtool, bb, git, opts, group):
    if opts['skip_compilation']:
        W(" %s: Compilation was skipped by user choice!" % group['name'])
        return

    for machine in opts['machines']:
        I(" %s: compiling upgraded version for %s ..." % (group['name'], machine))
        _compile(bb, " ".join([pkg_ctx['PN'] for pkg_ctx in group['pkgs']]), machine, group['workdir'])
        if opts['buildhistory'] and machine == opts['machines'][0]:
            I(" %s: Checking buildhistory ..." % group['name'])
            group['buildhistory'].diff()

def _rm_source_tree(devtool_output):
    for line in devtool_output.split("\n"):
        if line.startswith("NOTE: Leaving source tree"):
            srctree = line.split()[4]
            shutil.rmtree(srctree)

def devtool_finish(devtool, bb, git, opts, group):
    try:
        for p in group['pkgs']:
            devtool_output = devtool.finish(p['PN'], p['recipe_dir'])
            D(" 'devtool finish' printed:\n%s" %(devtool_output))
    except DevtoolError as e1:
        try:
            devtool_output = devtool.reset()
        except DevtoolError as e2:
            pass
        raise e1

upgrade_steps = [
    (load_env, "Loading environment ..."),
    (buildhistory_init, None),
    (devtool_upgrade, "Running 'devtool upgrade' ..."),
    (devtool_finish, "Running 'devtool finish' ..."),
    (compile, None),
]
