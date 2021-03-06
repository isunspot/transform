# Copyright 2017 Google Inc. All Rights Reserved.
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
"""Tensorflow-transform ExampleProtoCoder tests."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import pickle
import sys

# Note that this needs to happen before any non-python imports, so we do it
# pretty early on.
if any(arg == '--proto_implementation_type=python' for arg in sys.argv):
  os.environ['PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION'] = 'python'
elif any(arg == '--proto_implementation_type=cpp' for arg in sys.argv):
  os.environ['PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION'] = 'cpp'
elif any(arg.startswith('--proto_implementation_type') for arg in sys.argv):
  raise ValueError('Unexpected value for --proto_implementation_type')

import numpy as np
import tensorflow as tf

from tensorflow_transform.coders import example_proto_coder
from tensorflow_transform.tf_metadata import dataset_schema

from google.protobuf.internal import api_implementation
from google.protobuf import text_format
import unittest



class ExampleProtoCoderTest(unittest.TestCase):

  _INPUT_SCHEMA = dataset_schema.from_feature_spec({
      'scalar_feature_1': tf.FixedLenFeature(shape=[], dtype=tf.int64),
      'scalar_feature_2': tf.FixedLenFeature(shape=[], dtype=tf.int64),
      'scalar_feature_3': tf.FixedLenFeature(shape=[], dtype=tf.float32),
      'varlen_feature_1': tf.VarLenFeature(dtype=tf.float32),
      '1d_vector_feature': tf.FixedLenFeature(shape=[0], dtype=tf.string),
      'varlen_feature_2': tf.VarLenFeature(dtype=tf.string),
      'sparse_feature': tf.SparseFeature('idx', 'value', tf.float32, 10),
  })


  def _assert_encode_decode(self, coder, expected_proto_text,
                            expected_decoded):
    example = tf.train.Example()
    text_format.Merge(expected_proto_text, example)
    data = example.SerializeToString()

    # Assert the data is decoded into the expected format.
    decoded = coder.decode(data)
    np.testing.assert_equal(expected_decoded, decoded)

    # Assert the decoded data can be encoded back into the original proto.
    encoded = coder.encode(decoded)
    parsed_example = tf.train.Example()
    parsed_example.ParseFromString(encoded)
    self.assertEqual(example, parsed_example)

    # Assert the data can be decoded from the encoded string.
    decoded_again = coder.decode(encoded)
    np.testing.assert_equal(expected_decoded, decoded_again)

  def _assert_decode_encode(self, coder, expected_proto_text,
                            expected_decoded):
    example = tf.train.Example()
    text_format.Merge(expected_proto_text, example)

    # Assert the expected decoded data can be encoded into the expected proto.
    encoded = coder.encode(expected_decoded)
    parsed_example = tf.train.Example()
    parsed_example.ParseFromString(encoded)
    self.assertEqual(example, parsed_example)

    # Assert the encoded data can be decoded into the original input.
    decoded = coder.decode(encoded)
    np.testing.assert_equal(expected_decoded, decoded)

    # Assert the decoded data can be encoded back into the expected proto.
    encoded_again = coder.encode(decoded)
    parsed_example_again = tf.train.Example()
    parsed_example_again.ParseFromString(encoded_again)
    np.testing.assert_equal(example, parsed_example_again)

  def test_example_proto_coder(self):
    # We use a single coder and invoke multiple encodes and decodes on it to
    # make sure that cache consistency is implemented properly.
    coder = example_proto_coder.ExampleProtoCoder(self._INPUT_SCHEMA)

    # Python types.
    example_proto_text = """
    features {
      feature { key: "scalar_feature_1" value { int64_list { value: [ 12 ] } } }
      feature { key: "varlen_feature_1"
                value { float_list { value: [ 89.0 ] } } }
      feature { key: "scalar_feature_2" value { int64_list { value: [ 12 ] } } }
      feature { key: "scalar_feature_3"
                value { float_list { value: [ 1.0 ] } } }
      feature { key: "1d_vector_feature"
                value { bytes_list { value: [ 'this is a ,text' ] } } }
      feature { key: "varlen_feature_2"
                value { bytes_list { value: [ 'female' ] } } }
      feature { key: "value" value { float_list { value: [ 12.0, 20.0 ] } } }
      feature { key: "idx" value { int64_list { value: [ 1, 4 ] } } }
    }
    """
    expected_decoded = {
        'scalar_feature_1': 12,
        'scalar_feature_2': 12,
        'scalar_feature_3': 1.0,
        'varlen_feature_1': [89.0],
        '1d_vector_feature': ['this is a ,text'],
        'varlen_feature_2': ['female'],
        'sparse_feature': ([12.0, 20.0], [1, 4])
    }
    self._assert_encode_decode(coder, example_proto_text, expected_decoded)
    self._assert_decode_encode(coder, example_proto_text, expected_decoded)

    # Numpy types (with different values from above).
    example_proto_text = """
    features {
      feature { key: "scalar_feature_1" value { int64_list { value: [ 13 ] } } }
      feature { key: "varlen_feature_1" value { float_list { } } }
      feature { key: "scalar_feature_2"
                value { int64_list { value: [ 214 ] } } }
      feature { key: "scalar_feature_3"
                value { float_list { value: [ 2.0 ] } } }
      feature { key: "1d_vector_feature"
                value { bytes_list { value: [ 'this is another ,text' ] } } }
      feature { key: "varlen_feature_2"
                value { bytes_list { value: [ 'male' ] } } }
      feature { key: "value" value { float_list { value: [ 13.0, 21.0 ] } } }
      feature { key: "idx" value { int64_list { value: [ 2, 5 ] } } }
    }
    """
    expected_decoded = {
        'scalar_feature_1': np.array(13),
        'scalar_feature_2': np.int32(214),
        'scalar_feature_3': np.array(2.0),
        'varlen_feature_1': np.array([]),
        '1d_vector_feature': np.array(['this is another ,text']),
        'varlen_feature_2': np.array(['male']),
        'sparse_feature': (np.array([13.0, 21.0]), np.array([2, 5]))
    }
    self._assert_encode_decode(coder, example_proto_text, expected_decoded)
    self._assert_decode_encode(coder, example_proto_text, expected_decoded)

  def test_example_proto_coder_picklable(self):
    coder = example_proto_coder.ExampleProtoCoder(self._INPUT_SCHEMA)

    example_proto_text = """
    features {
      feature { key: "scalar_feature_1" value { int64_list { value: [ 12 ] } } }
      feature { key: "varlen_feature_1"
                value { float_list { value: [ 89.0 ] } } }
      feature { key: "scalar_feature_2" value { int64_list { value: [ 12 ] } } }
      feature { key: "scalar_feature_3"
                value { float_list { value: [ 2.0 ] } } }
      feature { key: "1d_vector_feature"
                value { bytes_list { value: [ 'this is a ,text' ] } } }
      feature { key: "varlen_feature_2"
                value { bytes_list { value: [ 'female' ] } } }
      feature { key: "value" value { float_list { value: [ 12.0, 20.0 ] } } }
      feature { key: "idx" value { int64_list { value: [ 1, 4 ] } } }
    }
    """
    expected_decoded = {
        'scalar_feature_1': 12,
        'scalar_feature_2': 12,
        'scalar_feature_3': 2.0,
        'varlen_feature_1': [89.0],
        '1d_vector_feature': ['this is a ,text'],
        'varlen_feature_2': ['female'],
        'sparse_feature': ([12.0, 20.0], [1, 4])
    }

    # Ensure we can pickle right away.
    coder = pickle.loads(pickle.dumps(coder))
    self._assert_encode_decode(coder, example_proto_text, expected_decoded)
    self._assert_decode_encode(coder, example_proto_text, expected_decoded)

    #  And after use.
    coder = pickle.loads(pickle.dumps(coder))
    self._assert_encode_decode(coder, example_proto_text, expected_decoded)
    self._assert_decode_encode(coder, example_proto_text, expected_decoded)

if __name__ == '__main__':
  unittest.main()
