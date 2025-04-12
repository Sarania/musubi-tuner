#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Mar 10 16:47:29 2025

@author: blyss
"""
import torch
import torch.nn.functional as F
import av
from .taehv import TAEHV
from .utils import load_torch_file
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class LatentPreviewer():
    def __init__(self, args, original_latents, timesteps, device, dtype, model_type="hunyuan"):
        self.mode = "latent2rgb" if args.preview_vae is None else "taehv"
        logger.info(f"Initializing latent previewer with mode {self.mode}...")
        self.args = args
        self.model_type = model_type
        self.original_latents = original_latents
        self.timesteps_percent = timesteps / 1000
        self.device = device
        self.dtype = dtype if dtype != torch.float8_e4m3fn else torch.float16

        if self.mode == "taehv":
            logger.info(f"Loading model {args.preview_vae}...")
            tae_sd = load_torch_file(args.preview_vae, safe_load=True, device=args.device)
            self.taehv = TAEHV(tae_sd).to(self.device, self.dtype)
            self.decoder = self.decode_taehv
            self.scale_factor = None
            self.fps = args.fps
        elif self.mode == "latent2rgb":
            self.decoder = self.decode_latent2rgb
            self.scale_factor = 8
            self.fps = int(args.fps / 4)

    def preview(self, noisy_latents, current_step):
        if self.model_type == "wan":
            noisy_latents = noisy_latents.unsqueeze(0)  # F, C, H, W -> B, F, C, H, W
        elif self.model_type == "hunyuan":
            pass  # already B, F, C, H, W
        denoisy_latents = self.subtract_original_and_normalize(noisy_latents, current_step)
        decoded = self.decoder(denoisy_latents, current_step)  # returned as F, C, H, W

        # Upscale if we used latent2rgb so output is same size as expected
        if self.scale_factor is not None:
            upscaled = F.interpolate(
                decoded,
                scale_factor=self.scale_factor,
                mode="bicubic",
                align_corners=False
            )
        else:
            upscaled = decoded

        _, _, h_up, w_up = upscaled.shape
        self.write_video(upscaled, w_up, h_up)

    def subtract_original_and_normalize(self, noisy_latents, current_step):
        # Compute what percent of original noise is remaining
        noise_remaining = self.timesteps_percent[current_step].to(device=noisy_latents.device)

        # Subtract the portion of original latents
        denoisy_latents = noisy_latents - (self.original_latents.to(device=noisy_latents.device) * noise_remaining)

        # Normalize
        normalized_denoisy_latents = (denoisy_latents - denoisy_latents.mean()) / (denoisy_latents.std() + 1e-5)
        return normalized_denoisy_latents

    def write_video(self, frames, width, height, target="./latent_preview.mp4"):
        # Check if we only have a single frame.
        if frames.shape[0] == 1:
            from PIL import Image
            # Clamp, scale, convert to byte and move to CPU
            frame = frames[0].clamp(0, 1).mul(255).byte().cpu()
            # Permute from (3, H, W) to (H, W, 3) for PIL.
            frame_np = frame.permute(1, 2, 0).numpy()
            # Change the target filename from .mp4 to .png
            target_img = target.replace(".mp4", ".png")
            Image.fromarray(frame_np).save(target_img)
            return

        # Otherwise, write out as a video.
        target_video = target.replace(".png", ".mp4")  # in case the user is reusing commands and forgets
        container = av.open(target_video, mode="w")
        stream = container.add_stream("libx264", rate=self.fps)
        stream.pix_fmt = "yuv420p"
        stream.width = width
        stream.height = height

        # Loop through each frame.
        for frame in frames:
            # Clamp to [0,1], scale, convert to byte and move to CPU.
            frame = frame.clamp(0, 1).mul(255).byte().cpu()
            # Permute from (3, H, W) -> (H, W, 3) for AV.
            frame_np = frame.permute(1, 2, 0).numpy()
            video_frame = av.VideoFrame.from_ndarray(frame_np, format="rgb24")
            for packet in stream.encode(video_frame):
                container.mux(packet)

        # Flush out any remaining packets and close.
        for packet in stream.encode():
            container.mux(packet)
        container.close()

    def decode_taehv(self, latents, current_step):
        """
        Decodes latents with the TAEHV model, returns shape (F, C, H, W).
        """

        with torch.no_grad():
            latents_permuted = latents.permute(0, 2, 1, 3, 4)  # Reordered to B, F, C, H, W for TAE
            latents_permuted = latents_permuted.to(device=self.device, dtype=self.dtype)
            decoded = self.taehv.decode_video(latents_permuted, parallel=False, show_progress_bar=False)
        return decoded.squeeze(0)  # squeeze off batch dimension as next step doesn't want it

    def decode_latent2rgb(self, latents, current_step):
        """
        Decodes latents to RGB using linear transform, returns shape (F, 3, H, W).
        """
        model_params = {
            "hunyuan": {
                "rgb_factors": [
                    [-0.0395, -0.0331,  0.0445],
                    [ 0.0696,  0.0795,  0.0518],
                    [ 0.0135, -0.0945, -0.0282],
                    [ 0.0108, -0.0250, -0.0765],
                    [-0.0209,  0.0032,  0.0224],
                    [-0.0804, -0.0254, -0.0639],
                    [-0.0991,  0.0271, -0.0669],
                    [-0.0646, -0.0422, -0.0400],
                    [-0.0696, -0.0595, -0.0894],
                    [-0.0799, -0.0208, -0.0375],
                    [ 0.1166,  0.1627,  0.0962],
                    [ 0.1165,  0.0432,  0.0407],
                    [-0.2315, -0.1920, -0.1355],
                    [-0.0270,  0.0401, -0.0821],
                    [-0.0616, -0.0997, -0.0727],
                    [ 0.0249, -0.0469, -0.1703]
                ],
                "bias": [0.0259, -0.0192, -0.0761],
            },
            "wan": {
                "rgb_factors": [
                    [-0.1299, -0.1692,  0.2932],
                    [ 0.0671,  0.0406,  0.0442],
                    [ 0.3568,  0.2548,  0.1747],
                    [ 0.0372,  0.2344,  0.1420],
                    [ 0.0313,  0.0189, -0.0328],
                    [ 0.0296, -0.0956, -0.0665],
                    [-0.3477, -0.4059, -0.2925],
                    [ 0.0166,  0.1902,  0.1975],
                    [-0.0412,  0.0267, -0.1364],
                    [-0.1293,  0.0740,  0.1636],
                    [ 0.0680,  0.3019,  0.1128],
                    [ 0.0032,  0.0581,  0.0639],
                    [-0.1251,  0.0927,  0.1699],
                    [ 0.0060, -0.0633,  0.0005],
                    [ 0.3477,  0.2275,  0.2950],
                    [ 0.1984,  0.0913,  0.1861]
                ],
                "bias": [-0.1835, -0.0868, -0.3360],
            },
        }

        if self.model_type not in model_params:
            raise ValueError(f"Unsupported model type: {self.model_type}")

        latent_rgb_factors = model_params[self.model_type]["rgb_factors"]
        latent_rgb_factors_bias = model_params[self.model_type]["bias"]

        # Prepare linear transform
        latent_rgb_factors = torch.tensor(
            latent_rgb_factors,
            device=latents.device,
            dtype=latents.dtype
        ).transpose(0, 1)
        latent_rgb_factors_bias = torch.tensor(
            latent_rgb_factors_bias,
            device=latents.device,
            dtype=latents.dtype
        )

        # For each frame, apply the linear transform
        latent_images = []
        for t in range(latents.shape[2]):
            extracted = latents[:, :, t, :, :][0].permute(1, 2, 0)  # shape = (H, W, C) after .permute(1,2,0)
            rgb = torch.nn.functional.linear(extracted, latent_rgb_factors, bias=latent_rgb_factors_bias)  # shape = (H, W, 3) after linear
            latent_images.append(rgb)

        # Stack frames into (F, H, W, 3)
        latent_images = torch.stack(latent_images, dim=0)

        # Normalize to [0..1]
        latent_images_min = latent_images.min()
        latent_images_max = latent_images.max()
        if latent_images_max > latent_images_min:
            latent_images = (latent_images - latent_images_min) / (latent_images_max - latent_images_min)

        # Permute to (F, 3, H, W) before returning
        latent_images = latent_images.permute(0, 3, 1, 2)
        return latent_images
