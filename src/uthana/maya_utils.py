"""Maya-specific utility functions for Uthana plugin."""

from datetime import datetime

import maya.cmds as cmds


def validate_maya_scene():
    """Check that the Maya scene is valid for operations.

    Returns:
        bool: True if scene is usable
    """
    try:
        return cmds.ls(type="transform") is not None
    except Exception:
        return False


def ensure_fbx_plugin():
    """Ensure the FBX plugin is loaded."""
    if not cmds.pluginInfo("fbxmaya", query=True, loaded=True):
        cmds.loadPlugin("fbxmaya")


def get_selected_joints():
    """Get all selected joint hierarchies.

    Returns:
        list: List of selected joint root nodes
    """
    selected = cmds.ls(selection=True, type="joint")
    if not selected:
        return []

    # Find root joints for each selection
    roots = set()
    for joint in selected:
        root = get_root_joint(joint)
        roots.add(root)

    return list(roots)


def get_root_joint(joint_name):
    """Find the root joint of a joint hierarchy.

    Args:
        joint_name: Name of any joint in the hierarchy

    Returns:
        Name of the root joint
    """
    current = joint_name
    while True:
        parents = cmds.listRelatives(current, parent=True, type="joint") or []
        if not parents:
            return current
        current = parents[0]


def get_frame_range():
    """Get the current playback frame range.

    Returns:
        tuple: (start_frame, end_frame)
    """
    start = cmds.playbackOptions(query=True, minTime=True)
    end = cmds.playbackOptions(query=True, maxTime=True)
    return (int(start), int(end))


def get_selected_joint_hierarchies():
    """Get the full hierarchy for each selected joint root.

    Returns:
        list: List of (root_joint, all_joints_in_hierarchy) tuples
    """
    roots = get_selected_joints()
    hierarchies = []
    for root in roots:
        all_joints = cmds.listRelatives(root, allDescendents=True, type="joint") or []
        all_joints = [root] + all_joints
        hierarchies.append((root, all_joints))
    return hierarchies


def generate_timestamp_filename(ext="fbx"):
    """Generate a filename with a timestamp.

    Args:
        ext: File extension (without dot)

    Returns:
        Filename string like "20240115_143052.fbx"
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{timestamp}.{ext}"


def build_web_viewer_url(domain, character_id, motion_id):
    """Build the web viewer URL for previewing a motion in browser.

    Args:
        domain: API domain (e.g., "uthana.com")
        character_id: Character ID
        motion_id: Motion ID

    Returns:
        Full URL to web viewer
    """
    return f"https://{domain}/app/play/{character_id}/{motion_id}"
