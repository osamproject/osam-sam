import numpy as np
import PIL.Image
from osam_core import apis
from osam_core import types


class Sam(types.Model):
    _image_size: int = 1024

    def encode_image(self, image: np.ndarray):
        if image.ndim == 2:
            raise ValueError("Grayscale images are not supported")
        if image.ndim == 3 and image.shape[2] == 4:
            raise ValueError("RGBA images are not supported")

        image_embedding = _compute_image_embedding(
            encoder_session=self._inference_sessions["encoder"],
            image=image,
            image_size=self._image_size,
        )

        return types.ImageEmbedding(
            original_height=image.shape[0],
            original_width=image.shape[1],
            embedding=image_embedding,
        )

    def generate_mask(
        self,
        image_embedding: types.ImageEmbedding,
        prompt: types.Prompt,
    ) -> np.ndarray:
        return _generate_mask(
            decoder_session=self._inference_sessions["decoder"],
            image_embedding=image_embedding,
            prompt=prompt,
            image_size=self._image_size,
        )


def _compute_scale_to_resize_image(height: int, width: int, image_size: int):
    if width > height:
        scale = image_size / width
        new_height = int(round(height * scale))
        new_width = image_size
    else:
        scale = image_size / height
        new_height = image_size
        new_width = int(round(width * scale))
    return scale, new_height, new_width


def _resize_image(image: np.ndarray, image_size: int):
    scale, new_height, new_width = _compute_scale_to_resize_image(
        height=image.shape[0],
        width=image.shape[1],
        image_size=image_size,
    )
    scaled_image = np.asarray(
        PIL.Image.fromarray(image).resize(
            (new_width, new_height), resample=PIL.Image.BILINEAR
        )
    ).astype(np.float32)
    return scale, scaled_image


def _compute_image_embedding(
    encoder_session,
    image: np.ndarray,
    image_size: int,
):
    scale, x = _resize_image(image=image, image_size=image_size)
    x = (x - np.array([123.675, 116.28, 103.53], dtype=np.float32)) / np.array(
        [58.395, 57.12, 57.375], dtype=np.float32
    )
    x = np.pad(
        x,
        (
            (0, image_size - x.shape[0]),
            (0, image_size - x.shape[1]),
            (0, 0),
        ),
    )
    x = x.transpose(2, 0, 1)[None, :, :, :]

    output = encoder_session.run(output_names=None, input_feed={"x": x})
    image_embedding = output[0][0]  # (embedding_dim, height, width)
    return image_embedding


def _generate_mask(
    decoder_session,
    image_embedding: types.ImageEmbedding,
    prompt: types.Prompt,
    image_size: int,
):
    onnx_coord = np.concatenate([prompt.points, np.array([[0.0, 0.0]])], axis=0)[
        None, :, :
    ]
    onnx_label = np.concatenate([prompt.point_labels, np.array([-1])], axis=0)[
        None, :
    ].astype(np.float32)

    scale, new_height, new_width = _compute_scale_to_resize_image(
        height=image_embedding.original_height,
        width=image_embedding.original_width,
        image_size=image_size,
    )
    onnx_coord = (
        onnx_coord.astype(float)
        * (
            new_width / image_embedding.original_width,
            new_height / image_embedding.original_height,
        )
    ).astype(np.float32)

    onnx_mask_input = np.zeros((1, 1, 256, 256), dtype=np.float32)
    onnx_has_mask_input = np.array([-1], dtype=np.float32)

    decoder_inputs = {
        "image_embeddings": image_embedding.embedding[None, :, :, :],
        "point_coords": onnx_coord,
        "point_labels": onnx_label,
        "mask_input": onnx_mask_input,
        "has_mask_input": onnx_has_mask_input,
        "orig_im_size": np.array(
            (image_embedding.original_height, image_embedding.original_width),
            dtype=np.float32,
        ),
    }

    masks, _, _ = decoder_session.run(None, decoder_inputs)
    mask = masks[0, 0]  # (1, 1, H, W) -> (H, W)
    mask = mask > 0.0
    return mask


class Sam91m(Sam):
    name = "sam:91m"

    _blobs = {
        "encoder": types.Blob(
            url="https://github.com/wkentaro/labelme/releases/download/sam-20230416/sam_vit_b_01ec64.quantized.encoder.onnx",
            hash="sha256:3346b9cc551c9902fbf3b203935e933592b22e042365f58321c17fc12641fd6a",
        ),
        "decoder": types.Blob(
            url="https://github.com/wkentaro/labelme/releases/download/sam-20230416/sam_vit_b_01ec64.quantized.decoder.onnx",
            hash="sha256:edbcf1a0afaa55621fb0abe6b3db1516818b609ea9368f309746a3afc68f7613",
        ),
    }


class Sam308m(Sam):
    name = "sam:308m"

    _blobs = {
        "encoder": types.Blob(
            url="https://github.com/wkentaro/labelme/releases/download/sam-20230416/sam_vit_l_0b3195.quantized.encoder.onnx",
            hash="sha256:f7158a4a1fe7f670ef47ea2f7f852685425c1ed6caa40f5df86cbe2b0502034f",
        ),
        "decoder": types.Blob(
            url="https://github.com/wkentaro/labelme/releases/download/sam-20230416/sam_vit_l_0b3195.quantized.decoder.onnx",
            hash="sha256:552ebb23bf52c5e5b971ac710d1eb8dccfd88b36cc6aff881d1536d1662e6d7b",
        ),
    }


class Sam636m(Sam):
    name = "sam:latest"

    _blobs = {
        "encoder": types.Blob(
            url="https://github.com/wkentaro/labelme/releases/download/sam-20230416/sam_vit_h_4b8939.quantized.encoder.onnx",
            hash="sha256:a5c745fd4279efc5e5436b412200e983dafc2249ce172af6cc0002a71bb5f485",
        ),
        "decoder": types.Blob(
            url="https://github.com/wkentaro/labelme/releases/download/sam-20230416/sam_vit_h_4b8939.quantized.decoder.onnx",
            hash="sha256:020b385a45ffe51097e1acd10cd791075a86171153505f789a793bc382eef210",
        ),
    }


apis.register_model_type(Sam91m)
apis.register_model_type(Sam308m)
apis.register_model_type(Sam636m)
