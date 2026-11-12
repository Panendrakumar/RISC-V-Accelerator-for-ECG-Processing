"""Rebuild the project's selected ECG Transformer for inference-only use.

The architecture mirrors ``build_baseline_ViT`` in the saved training notebook.
This module never trains or downloads data.  It provides a stable source model
for later parameter export and fixed-point / RTL comparisons.
"""

from pathlib import Path

import tensorflow as tf


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = (
    PROJECT_ROOT
    / "04_Model_Software"
    / "third_party_models"
    / "TinyTransformer"
    / "software"
)
CHECKPOINT = (
    MODEL_DIR
    / "training_attempt_20261024"
    / "baseline_ecg_transformer.weights.h5"
)

NUM_CLASSES = 5
ECG_SAMPLES = 198
RR_FEATURES = 2
NUM_HEADS = 8
KEY_DIM = 2
EMBEDDING_DIM = 16
MLP_DIM = 128
NUM_PATCHES = 66
EXPECTED_PARAMETER_COUNT = 6643
CLASS_ORDER = ("N", "S", "V", "F", "Q")


class AddPositionEmbs(tf.keras.layers.Layer):
    """Learned positional embedding layer used by the reference notebook."""

    def __init__(self, posemb_init=None, **kwargs):
        super().__init__(**kwargs)
        self.posemb_init = posemb_init

    def build(self, input_shape):
        self.pos_embedding = self.add_weight(
            name="pos_embedding",
            shape=(1, input_shape[1], input_shape[2]),
            initializer=self.posemb_init,
            trainable=True,
        )
        super().build(input_shape)

    def call(self, inputs):
        return inputs + tf.cast(self.pos_embedding, inputs.dtype)


def _encoder_block(inputs):
    normalized = tf.keras.layers.LayerNormalization(dtype=inputs.dtype)(inputs)
    attended = tf.keras.layers.MultiHeadAttention(
        num_heads=NUM_HEADS,
        key_dim=KEY_DIM,
        dropout=0.1,
    )(normalized, normalized)
    residual = tf.keras.layers.Add()([attended, inputs])

    normalized = tf.keras.layers.LayerNormalization(dtype=residual.dtype)(residual)
    hidden = tf.keras.layers.Dense(MLP_DIM, activation=tf.nn.gelu)(normalized)
    hidden = tf.keras.layers.Dropout(0.1)(hidden)
    projected = tf.keras.layers.Dense(
        EMBEDDING_DIM, activation=tf.nn.gelu
    )(hidden)
    projected = tf.keras.layers.Dropout(0.1)(projected)
    return tf.keras.layers.Add()([projected, residual])


def build_active_model():
    """Build the exact inference graph for the saved local checkpoint."""
    ecg_input = tf.keras.layers.Input(
        shape=(ECG_SAMPLES, 1, 1), name="x1"
    )
    rr_input = tf.keras.layers.Input(shape=(RR_FEATURES,), name="x2")

    patches = tf.keras.layers.Conv2D(
        filters=EMBEDDING_DIM,
        kernel_size=(3, 1),
        strides=(3, 1),
        padding="valid",
    )(ecg_input)
    patches = tf.keras.layers.Reshape((NUM_PATCHES, EMBEDDING_DIM))(patches)
    encoded = AddPositionEmbs(
        posemb_init=tf.keras.initializers.RandomNormal(stddev=0.02),
        name="posembed_input",
    )(patches)
    encoded = tf.keras.layers.Dropout(0.2)(encoded)

    encoded = _encoder_block(encoded)
    encoded = tf.keras.layers.LayerNormalization(name="encoder_norm")(encoded)
    pooled = tf.keras.layers.GlobalAveragePooling1D()(encoded)
    rr_embedding = tf.keras.layers.Dense(2, use_bias=False)(rr_input)
    combined = tf.keras.layers.Concatenate()([pooled, rr_embedding])
    logits = tf.keras.layers.Dense(
        NUM_CLASSES,
        name="head",
        kernel_initializer=tf.keras.initializers.Zeros(),
    )(combined)

    return tf.keras.Model(inputs=[ecg_input, rr_input], outputs=logits)


def load_active_model(checkpoint=CHECKPOINT):
    """Build and load the saved best checkpoint without starting training."""
    model = build_active_model()
    if model.count_params() != EXPECTED_PARAMETER_COUNT:
        raise RuntimeError(
            f"Reference graph has {model.count_params()} parameters; expected "
            f"{EXPECTED_PARAMETER_COUNT}. Check the notebook architecture."
        )
    checkpoint = Path(checkpoint)
    if not checkpoint.is_file():
        raise FileNotFoundError(f"Saved model checkpoint not found: {checkpoint}")
    model.load_weights(checkpoint)
    return model
