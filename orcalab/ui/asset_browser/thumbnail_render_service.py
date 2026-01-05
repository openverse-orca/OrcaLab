import asyncio
import logging
from math import sqrt, cos, sin, tan, pi
from PIL import Image
from scipy.spatial.transform import Rotation
from orcalab.actor import AssetActor

logger = logging.getLogger(__name__)
from orcalab.http_service.http_bus import HttpServiceRequestBus
from orcalab.metadata_service_bus import MetadataServiceRequestBus
from orcalab.scene_edit_bus import SceneEditNotificationBus, SceneEditRequestBus
from orcalab.ui.asset_browser.thumbnail_render_bus import ThumbnailRenderRequest, ThumbnailRenderRequestBus, ThumbnailRenderNotification, ThumbnailRenderNotificationBus
from orcalab.application_bus import ApplicationRequestBus
from orcalab.path import Path
from typing import override
import numpy as np
from orcalab.math import Transform
import os
from orcalab.ui.image_utils import ImageProcessor

class ThumbnailRenderService(ThumbnailRenderRequest):
    def __init__(self):
        super().__init__()
        ThumbnailRenderRequestBus.connect(self)
        self.tan_33_5 = tan(33.5 * pi/180)
        self.cos_15 = cos(15 * pi/180)
        self.sin_15 = sin(15 * pi/180)
        self.quat = Rotation.from_euler("xyz", [-15, 0, 0], degrees=True).as_quat()[[3, 0, 1, 2]]

    @override
    async def render_thumbnail(self, asset_paths: list[str]) -> None:

        actor_camera1080 = await self._add_camera("mujococamera1080")
        actor_camera256 = await self._add_camera("mujococamera256")
        actor_camera512 = await self._add_camera("mujococamera512")

        if actor_camera1080 is None or actor_camera256 is None or actor_camera512 is None:
            print("failed to add cameras to scene")
            return None
        for asset_path in asset_paths:   
            await self._create_panorama_apng(asset_path, actor_camera1080, actor_camera256, actor_camera512)

        await SceneEditRequestBus().delete_actor(actor_camera512, undo=False, source="create_panorama_apng")
        await SceneEditRequestBus().delete_actor(actor_camera256, undo=False, source="create_panorama_apng")
        await SceneEditRequestBus().delete_actor(actor_camera1080, undo=False, source="create_panorama_apng")
    
    async def _create_panorama_apng(self, asset_path: str, actor_camera1080: AssetActor, actor_camera256: AssetActor, actor_camera512: AssetActor) -> None:
        actor_out = []
        await ApplicationRequestBus().add_item_to_scene(asset_path, output=actor_out)
        if not actor_out:
            logger.error(f"failed to add {asset_path} to scene")
            return
        actor = actor_out[0]

        aabb = []
        await SceneEditNotificationBus().get_actor_asset_aabb(Path(f"/{actor.name}"), output=aabb)
        if not aabb:
            logger.error(f"failed to get {asset_path} aabb")
            return 
        new_aabb, scale = self._get_actor_position_scale(aabb)
        await SceneEditRequestBus().set_transform(actor, Transform(position=np.array([0, 0, -aabb[2] * scale]), rotation=self.quat, scale=scale), local=True, undo=False, source="create_panorama_apng")
        transform = self._get_camera_position(new_aabb)

        await SceneEditRequestBus().set_transform(actor_camera1080, transform, local=True, undo=False, source="create_panorama_apng")
        await SceneEditRequestBus().set_transform(actor_camera256, transform, local=True, undo=False, source="create_panorama_apng")
        await SceneEditRequestBus().set_transform(actor_camera512, transform, local=True, undo=False, source="create_panorama_apng")

        tmp_path = os.path.join(os.path.expanduser("~"), ".orcalab", "tmp", asset_path)
        dir_path = os.path.dirname(tmp_path)
        await SceneEditNotificationBus().get_camera_png("mujococamera1080", dir_path, f"{os.path.basename(tmp_path)}_1080.png")

        png_files, png_512_files = [], []
        for rotation_z in range(0, 360, 24):
            quat = Rotation.from_euler("xyz", [0, 0, rotation_z], degrees=True).as_quat()[[3, 0, 1, 2]]
            await SceneEditRequestBus().set_transform(actor, Transform(position=np.array([0, 0, -aabb[2] * scale]), rotation=quat, scale=scale), local=True, undo=False, source="create_panorama_apng")
            png_filename = f"{os.path.basename(tmp_path)}_256_{rotation_z}.png"
            if rotation_z % 72 == 0:
                png_512_filename = f"{os.path.basename(tmp_path)}_{rotation_z}_512.png"
                await SceneEditNotificationBus().get_camera_png("mujococamera512", dir_path, png_512_filename)
                png_512_path = os.path.join(dir_path, png_512_filename)
                png_512_files.append(png_512_path)
            await SceneEditNotificationBus().get_camera_png("mujococamera256", dir_path, png_filename)
            png_files.append(os.path.join(dir_path, png_filename))

        await asyncio.sleep(0.01)
        apng_path = os.path.join(dir_path, f"{os.path.basename(tmp_path)}_panorama.apng")


        for png_512_file in png_512_files:
            retry = 0
            aabb_text = f"AABB: [{aabb[0]:.2f}, {aabb[1]:.2f}, {aabb[2]:.2f}]\n      [{aabb[3]:.2f}, {aabb[4]:.2f}, {aabb[5]:.2f}]"
            while retry < 10:
                if ImageProcessor.add_text_to_image(png_512_file, aabb_text, position="bottom_right", font_size=10):
                    break
                retry += 1
                await asyncio.sleep(0.01)

        images = []
        for png_file in png_files:
            retry = 0
            while retry < 10:
                if os.path.exists(png_file):
                    try:
                        img = Image.open(png_file)
                        images.append(img)
                        break
                    except Exception as e:
                        retry += 1
                        await asyncio.sleep(0.01)
                else:
                    await asyncio.sleep(0.01)
                    retry += 1

        if images:
            apng_path = os.path.join(dir_path, f"{os.path.basename(tmp_path)}_panorama.apng")
            try:
                success = ImageProcessor.create_apng_panorama(images, apng_path, duration=200)
                if success:
                    print(f"actor {asset_path} panorama APNG created")
                else:
                    print(f"actor {asset_path} panorama APNG creation failed")
            finally:
                for img in images:
                    try:
                        img.close()
                    except Exception:
                        pass

            for png_file in png_files:
                if os.path.exists(png_file):
                    try:
                        os.remove(png_file)
                    except OSError as e:
                        continue
        await SceneEditRequestBus().delete_actor(actor, undo=False, source="create_panorama_apng")

        logger.info(f"uploading {asset_path} thumbnail to server")
        asset_metadata = []
        MetadataServiceRequestBus().get_asset_info(asset_path, output=asset_metadata)
        if not asset_metadata or asset_metadata[0] is None:
            logger.info(f"{asset_path} not in metadata")
            return 
        asset_info = asset_metadata[0]
        
        png_1080_path = os.path.join(dir_path, f"{os.path.basename(tmp_path)}_1080.png")
        files = [png_1080_path, apng_path] + png_512_files
        await HttpServiceRequestBus().post_asset_thumbnail(asset_info['id'], files)
            
    # 相机位置计算公式
    def _get_camera_position(self, aabb: list[float]) -> Transform:
        x = (aabb[0]+aabb[3])/2
        r = sqrt((aabb[3]-aabb[0])**2 + (aabb[4]-aabb[1])**2 + (aabb[5]-aabb[2])**2) / 2 * 1.1
        y0 = r / self.tan_33_5
        y = -y0 * self.cos_15
        z = (aabb[2] + aabb[5])/2 + r * self.sin_15 / self.tan_33_5
        position = [x, y, z]
        return Transform(position=np.array(position), rotation=self.quat, scale=1.0)

    # 对actor进行缩放
    def _get_actor_position_scale(self, aabb: list[float]):
        max_dim = max(aabb[3]-aabb[0], aabb[4]-aabb[1], aabb[5]-aabb[2])
        scale = 1 / max_dim
        new_aabb = [scale * value for value in aabb]
        new_aabb[5] -= new_aabb[2]
        new_aabb[2] = 0
        return new_aabb, scale

    async def _add_camera(self, camera_name: str) -> AssetActor:
        actor = []
        await ApplicationRequestBus().add_item_to_scene_with_transform(camera_name, f"prefabs/{camera_name}", parent_path=Path.root_path(), transform=Transform(position=np.array([0, -2.5, 2]), rotation=self.quat, scale=1.0), output=actor)
        if not actor:
            print(f"failed to add {camera_name} to scene")
            return None
        return actor[0]

class ThumbnailRenderNotificationService(ThumbnailRenderNotification):
    def __init__(self):
        super().__init__()
        ThumbnailRenderNotificationBus.connect(self)

    @override
    def on_thumbnail_rendered(self, asset_path: str, thumbnail_path: str) -> None:
        pass