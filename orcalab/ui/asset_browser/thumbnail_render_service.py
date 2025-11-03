import asyncio
from PIL import Image
from scipy.spatial.transform import Rotation
from orcalab.actor import AssetActor
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

    @override
    async def render_thumbnail(self, asset_paths: list[str]) -> None:
        actor_camera1080 = []
        quat = Rotation.from_euler("xyz", [-15, 0, 0], degrees=True).as_quat()[[3, 0, 1, 2]]
        await ApplicationRequestBus().add_item_to_scene_with_transform("mujococamera1080", "prefabs/mujococamera1080", parent_path=Path.root_path(), transform=Transform(position=np.array([0, -2.5, 2]), rotation=quat, scale=1.0), output=actor_camera1080)
        if not actor_camera1080:
            print(f"failed to add mujococamera1080 to scene")
            return
        actor_camera1080 = actor_camera1080[0]

        actor_camera256 = []
        await ApplicationRequestBus().add_item_to_scene_with_transform("mujococamera256", "prefabs/mujococamera256", parent_path=Path.root_path(), transform=Transform(position=np.array([0, -2.5, 2]), rotation=quat, scale=1.0), output=actor_camera256)
        if not actor_camera256:
            print(f"failed to add mujococamera256 to scene")
            return
        actor_camera256 = actor_camera256[0]
        for asset_path in asset_paths:   
            await self._create_panorama_apng(asset_path)


        await SceneEditRequestBus().delete_actor(actor_camera256, undo=False, source="create_panorama_apng")
        await SceneEditRequestBus().delete_actor(actor_camera1080, undo=False, source="create_panorama_apng")
    
    async def _create_panorama_apng(self, asset_path: str) -> None:
        actor_out = []
        await ApplicationRequestBus().add_item_to_scene(asset_path, output=actor_out)
        if not actor_out:
            print(f"failed to add {asset_path} to scene")
            return
        actor = actor_out[0]

        tmp_path = os.path.join(os.path.expanduser("~"), ".orcalab", "tmp", asset_path)
        dir_path = os.path.dirname(tmp_path)
        await SceneEditNotificationBus().get_camera_png("mujococamera1080", dir_path, f"{os.path.basename(tmp_path)}_1080.png")

        png_files = []
        for rotation_z in range(0, 360, 24):
            quat = Rotation.from_euler("xyz", [0, 0, rotation_z], degrees=True).as_quat()[[3, 0, 1, 2]]
            await SceneEditRequestBus().set_transform(actor, Transform(position=np.array([0, 0, 0]), rotation=quat, scale=1.0), local=True, undo=False, source="create_panorama_apng")
            png_filename = f"{os.path.basename(tmp_path)}_256_{rotation_z}.png"
            await SceneEditNotificationBus().get_camera_png("mujococamera256", dir_path, png_filename)
            png_files.append(os.path.join(dir_path, png_filename))

        await asyncio.sleep(0.01)
        apng_path = os.path.join(dir_path, f"{os.path.basename(tmp_path)}_panorama.apng")

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
                        img.close()
                        retry += 1
                        await asyncio.sleep(0.01)
                else:
                    await asyncio.sleep(0.01)
                    retry += 1

        if images:
            apng_path = os.path.join(dir_path, f"{os.path.basename(tmp_path)}_panorama.apng")
            success = ImageProcessor.create_apng_panorama(images, apng_path, duration=200)
            if success:
                print(f"actor {asset_path} panorama APNG created")
            else:
                print(f"actor {asset_path} panorama APNG creation failed")

            for png_file in png_files:
                if os.path.exists(png_file):
                    try:
                        os.remove(png_file)
                    except OSError as e:
                        continue

        await SceneEditRequestBus().delete_actor(actor, undo=False, source="create_panorama_apng")




class ThumbnailRenderNotificationService(ThumbnailRenderNotification):
    def __init__(self):
        super().__init__()
        ThumbnailRenderNotificationBus.connect(self)

    @override
    def on_thumbnail_rendered(self, asset_path: str, thumbnail_path: str) -> None:
        pass