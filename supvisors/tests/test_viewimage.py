#!/usr/bin/python
#-*- coding: utf-8 -*-

# ======================================================================
# Copyright 2016 Julien LE CLEACH
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ======================================================================

import sys
import unittest


class ViewImageTest(unittest.TestCase):
    """ Test case for the viewimage module. """

    def test_stats_images(self):
        """ Test the values set at construction. """
        from supvisors.viewimage import address_image_contents, process_image_contents
        self.assertIsNotNone(address_image_contents)
        self.assertIsNotNone(process_image_contents)

    def test_address_image_view(self):
        """ Test the values set at construction. """
        from supvisors.viewimage import AddressImageView
        view = AddressImageView()
        self.assertIsNotNone(view)

    def test_process_image_view(self):
        """ Test the values set at construction. """
        from supvisors.viewimage import ProcessImageView
        view = ProcessImageView()
        self.assertIsNotNone(view)


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
