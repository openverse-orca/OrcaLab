from orcalab.application_bus import ApplicationRequestBus


def get_local_scene():
    from orcalab.local_scene import LocalScene

    local_scene_list = []
    ApplicationRequestBus().get_local_scene(local_scene_list)

    if local_scene_list and isinstance(local_scene_list[0], LocalScene):
        return local_scene_list[0]

    raise RuntimeError("Failed to get LocalScene from ApplicationRequestBus")


def get_remote_scene():
    from orcalab.remote_scene import RemoteScene

    remote_scene_list = []
    ApplicationRequestBus().get_remote_scene(remote_scene_list)

    if remote_scene_list and isinstance(remote_scene_list[0], RemoteScene):
        return remote_scene_list[0]

    raise RuntimeError("Failed to get RemoteScene from ApplicationRequestBus")
