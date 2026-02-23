"""Maya-specific motion pipeline for Uthana plugin.

Handles FBX import/export, animation baking, and motion workflows
using Maya's native commands and the fbxmaya plugin.
"""

from datetime import datetime
from pathlib import Path

import maya.cmds as cmds
import maya.mel as mel

from uthana import maya_utils
from uthana.core import client
from uthana.core.constants import CACHE_DIR
from uthana.core.logger import logger
from uthana.core.types import (
    DownloadRequest,
    ExportRequest,
    OperationResult,
    StitchRequest,
)


def import_fbx_to_maya(fbx_path, motion_id=None):
    """Import FBX file into Maya scene.

    Args:
        fbx_path: Path to the FBX file
        motion_id: Optional motion ID for namespace naming

    Returns:
        OperationResult with import details
    """
    try:
        maya_utils.ensure_fbx_plugin()

        # Track objects before import
        objects_before = set(cmds.ls(dag=True, long=True) or [])

        # Build namespace
        timestamp = datetime.now().strftime("%H%M%S")
        if motion_id:
            namespace = f"uthana_{timestamp}_{motion_id}"
        else:
            namespace = f"uthana_{timestamp}"

        # Sanitize namespace (Maya doesn't allow certain characters)
        namespace = namespace.replace("-", "_").replace(".", "_")

        # Set FBX import options
        mel.eval('FBXImportMode -v "add"')
        mel.eval("FBXImportFillTimeline -v true")
        mel.eval("FBXImportSetLockedAttribute -v false")

        # Import the file
        cmds.file(
            fbx_path,
            i=True,
            type="FBX",
            ignoreVersion=True,
            renameAll=True,
            mergeNamespacesOnClash=False,
            namespace=namespace,
            options="fbx",
        )

        # Find new objects
        objects_after = set(cmds.ls(dag=True, long=True) or [])
        new_objects = list(objects_after - objects_before)

        logger.info("FBX imported: %s (%d new objects)", Path(fbx_path).name, len(new_objects))

        return OperationResult(
            success=True,
            message=f"FBX imported: {Path(fbx_path).name}",
            data={
                "file_path": fbx_path,
                "new_objects": new_objects,
                "namespace": namespace,
            },
        )

    except Exception as e:
        logger.error("FBX import failed: %s", str(e))
        return OperationResult(success=False, message=f"FBX import failed: {str(e)}")


def download_and_import_motion(domain, api_key, character_id, motion_id):
    """Download motion FBX from server and import into Maya.

    Args:
        domain: API domain
        api_key: API key
        character_id: Character ID
        motion_id: Motion ID

    Returns:
        OperationResult with import details
    """
    request = DownloadRequest(
        domain=domain,
        api_key=api_key,
        character_id=character_id,
        motion_id=motion_id,
    )

    download_result = client.download_motion_file(request)
    if not download_result.success:
        return download_result

    file_path = download_result.data.get("file_path")
    if not file_path:
        return OperationResult(success=False, message="No file path in download result")

    return import_fbx_to_maya(file_path, motion_id)


def export_joints_to_fbx(output_path, use_frame_range=True):
    """Export selected joint hierarchy to FBX.

    Args:
        output_path: Path for the output FBX file
        use_frame_range: If True, use playback range; if False, export all

    Returns:
        OperationResult with export details
    """
    try:
        maya_utils.ensure_fbx_plugin()

        # Get selected joints
        selected = cmds.ls(selection=True, type="joint")
        if not selected:
            return OperationResult(success=False, message="No joints selected")

        # Find root joint
        root_joint = maya_utils.get_root_joint(selected[0])

        # Select the full hierarchy
        cmds.select(root_joint, hierarchy=True)

        # Also select skinned meshes parented to or skinned to this skeleton
        skin_clusters = cmds.ls(type="skinCluster") or []
        mesh_objects = []
        for sc in skin_clusters:
            influences = cmds.skinCluster(sc, query=True, influence=True) or []
            if root_joint in influences or any(
                j in influences
                for j in (cmds.listRelatives(root_joint, allDescendents=True, type="joint") or [])
            ):
                geometry = cmds.skinCluster(sc, query=True, geometry=True) or []
                mesh_objects.extend(geometry)

        for mesh in mesh_objects:
            cmds.select(mesh, add=True)

        # Set FBX export options
        if use_frame_range:
            start, end = maya_utils.get_frame_range()
            mel.eval(f"FBXExportBakeComplexStart -v {int(start)}")
            mel.eval(f"FBXExportBakeComplexEnd -v {int(end)}")
        else:
            # Use full animation range
            start = cmds.playbackOptions(query=True, animationStartTime=True)
            end = cmds.playbackOptions(query=True, animationEndTime=True)
            mel.eval(f"FBXExportBakeComplexStart -v {int(start)}")
            mel.eval(f"FBXExportBakeComplexEnd -v {int(end)}")

        mel.eval("FBXExportBakeComplexAnimation -v true")
        mel.eval("FBXExportConstraints -v false")
        mel.eval("FBXExportCameras -v false")
        mel.eval("FBXExportLights -v false")
        mel.eval("FBXExportInputConnections -v false")
        mel.eval('FBXExportUpAxis "y"')
        mel.eval("FBXExportSkins -v true")
        mel.eval("FBXExportShapes -v false")

        # Export
        cmds.file(
            output_path,
            exportSelected=True,
            type="FBX export",
            force=True,
        )

        if not Path(output_path).exists():
            return OperationResult(
                success=False, message=f"FBX file was not created at {output_path}"
            )

        file_size = Path(output_path).stat().st_size
        logger.info("FBX exported: %s (%d bytes)", output_path, file_size)

        return OperationResult(
            success=True,
            message=f"FBX exported: {Path(output_path).name}",
            data={
                "file_path": output_path,
                "root_joint": root_joint,
                "file_size": file_size,
            },
        )

    except Exception as e:
        logger.error("FBX export failed: %s", str(e))
        return OperationResult(success=False, message=f"FBX export failed: {str(e)}")


def fbx_to_gltf(fbx_path):
    """Convert FBX to GLTF embedded format.

    Tries FBX2glTF command-line tool first, falls back to trimesh.

    Args:
        fbx_path: Path to the FBX file

    Returns:
        GLTF content as string, or None on failure
    """
    import shutil
    import subprocess

    gltf_path = fbx_path.replace(".fbx", ".gltf")

    # Option 1: FBX2glTF binary
    fbx2gltf = shutil.which("FBX2glTF")
    if fbx2gltf:
        try:
            subprocess.run(
                [fbx2gltf, "-i", fbx_path, "-o", gltf_path, "--embed"],
                check=True,
                capture_output=True,
                timeout=60,
            )
            with open(gltf_path, "r") as f:
                return f.read()
        except Exception as e:
            logger.warning("FBX2glTF failed: %s", e)

    # Option 2: trimesh library
    try:
        import trimesh

        scene = trimesh.load(fbx_path)
        gltf_data = trimesh.exchange.gltf.export_glb(scene)
        # Note: this produces GLB, not embedded GLTF
        # For the API, we may need the text GLTF
        with open(gltf_path, "wb") as f:
            f.write(gltf_data)
        logger.info("Converted FBX to GLTF using trimesh")
        with open(gltf_path, "r", errors="ignore") as f:
            return f.read()
    except ImportError:
        pass
    except Exception as e:
        logger.warning("trimesh conversion failed: %s", e)

    return None


def bake_and_upload_motion(request):
    """Complete pipeline: export from Maya -> convert to GLTF -> upload -> download -> import.

    Args:
        request: BakeAndUploadRequest

    Returns:
        OperationResult
    """
    if not maya_utils.validate_maya_scene():
        return OperationResult(success=False, message="Invalid Maya scene")

    if not request.character_id.strip():
        return OperationResult(success=False, message="Character ID is required")

    # Export selected joints to FBX
    filename = maya_utils.generate_timestamp_filename(ext="fbx")
    fbx_path = str(CACHE_DIR / filename)

    export_result = export_joints_to_fbx(fbx_path, request.use_frame_range)
    if not export_result.success:
        return export_result

    # Convert FBX to GLTF
    gltf_content = fbx_to_gltf(fbx_path)
    if not gltf_content:
        return OperationResult(
            success=False,
            message="Failed to convert FBX to GLTF. Install FBX2glTF or trimesh.",
        )

    # Upload GLTF
    export_request = ExportRequest(
        domain=request.domain,
        api_key=request.api_key,
        character_id=request.character_id,
        motion_name=Path(filename).stem,
        gltf_content=gltf_content,
    )

    upload_result = client.create_motion_from_gltf(export_request)
    if not upload_result.success:
        return upload_result

    motion_id = upload_result.data.get("motion_id")
    logger.info("Motion baked and uploaded: %s", motion_id)

    # Download and import the result
    import_result = download_and_import_motion(
        request.domain, request.api_key, request.character_id, motion_id
    )

    if import_result.success:
        return OperationResult(
            success=True,
            message=f"Motion baked, uploaded and imported! ID: {motion_id}",
            data={"motion_id": motion_id},
        )
    else:
        return OperationResult(
            success=True,
            message=f"Motion baked and uploaded! ID: {motion_id}. "
            f"Import failed: {import_result.message}",
            data={"motion_id": motion_id},
        )


def bake_specific_joint_hierarchy(root_joint, character_id, domain, api_key, use_frame_range=True):
    """Bake a specific joint hierarchy to FBX, convert to GLTF, upload, and return motion_id.

    Used by stitch operations to bake individual joint hierarchies.

    Args:
        root_joint: Root joint name
        character_id: Character ID
        domain: API domain
        api_key: API key
        use_frame_range: Whether to use playback frame range

    Returns:
        OperationResult with motion_id in data
    """
    # Save current selection
    original_selection = cmds.ls(selection=True)

    try:
        # Select the target joint hierarchy
        cmds.select(root_joint, hierarchy=True)

        # Export to FBX
        filename = maya_utils.generate_timestamp_filename(ext="fbx")
        fbx_path = str(CACHE_DIR / filename)

        export_result = export_joints_to_fbx(fbx_path, use_frame_range)
        if not export_result.success:
            return export_result

        # Convert to GLTF
        gltf_content = fbx_to_gltf(fbx_path)
        if not gltf_content:
            return OperationResult(
                success=False,
                message="Failed to convert FBX to GLTF. Install FBX2glTF or trimesh.",
            )

        # Upload
        export_request = ExportRequest(
            domain=domain,
            api_key=api_key,
            character_id=character_id,
            motion_name=f"stitch_{Path(filename).stem}",
            gltf_content=gltf_content,
        )

        upload_result = client.create_motion_from_gltf(export_request)
        if not upload_result.success:
            return upload_result

        motion_id = upload_result.data.get("motion_id")
        return OperationResult(
            success=True,
            message=f"Joint hierarchy {root_joint} baked successfully",
            data={"motion_id": motion_id},
        )

    except Exception as e:
        return OperationResult(success=False, message=f"Bake failed: {str(e)}")
    finally:
        # Restore selection
        if original_selection:
            cmds.select(original_selection)
        else:
            cmds.select(clear=True)

        # Clean up temp file
        try:
            if Path(fbx_path).exists():
                Path(fbx_path).unlink()
        except Exception:
            pass


def stitch_motions(request):
    """Stitch two joint hierarchies together.

    User should have two joint roots selected. First selected = leading, second = trailing.

    Args:
        request: StitchMotionsRequest

    Returns:
        OperationResult
    """
    roots = maya_utils.get_selected_joints()
    if len(roots) < 2:
        return OperationResult(
            success=False,
            message="Select two joint roots to stitch (first = leading, second = trailing)",
        )

    leading_root = roots[0]
    trailing_root = roots[1]

    logger.info("Stitching: leading=%s, trailing=%s", leading_root, trailing_root)

    # Bake leading
    leading_result = bake_specific_joint_hierarchy(
        leading_root, request.character_id, request.domain, request.api_key, request.use_frame_range
    )
    if not leading_result.success:
        return OperationResult(
            success=False, message=f"Failed to bake leading: {leading_result.message}"
        )

    leading_motion_id = leading_result.data.get("motion_id")

    # Bake trailing
    trailing_result = bake_specific_joint_hierarchy(
        trailing_root,
        request.character_id,
        request.domain,
        request.api_key,
        request.use_frame_range,
    )
    if not trailing_result.success:
        return OperationResult(
            success=False, message=f"Failed to bake trailing: {trailing_result.message}"
        )

    trailing_motion_id = trailing_result.data.get("motion_id")

    # Stitch via API
    stitch_request = StitchRequest(
        domain=request.domain,
        api_key=request.api_key,
        character_id=request.character_id,
        leading_motion_id=leading_motion_id,
        trailing_motion_id=trailing_motion_id,
        duration=request.duration,
    )
    stitch_result = client.create_stitched_motion(stitch_request)

    if not stitch_result.success:
        return OperationResult(success=False, message=f"Stitch API failed: {stitch_result.message}")

    stitched_motion_id = stitch_result.data.get("motion_id")

    # Download and import
    import_result = download_and_import_motion(
        request.domain, request.api_key, request.character_id, stitched_motion_id
    )

    if import_result.success:
        return OperationResult(
            success=True,
            message=f"Motions stitched and imported! ID: {stitched_motion_id}",
            data={
                "stitched_motion_id": stitched_motion_id,
                "leading_motion_id": leading_motion_id,
                "trailing_motion_id": trailing_motion_id,
            },
        )
    else:
        return OperationResult(
            success=True,
            message=f"Motions stitched! ID: {stitched_motion_id}. "
            f"Import failed: {import_result.message}",
            data={"stitched_motion_id": stitched_motion_id},
        )


def stitch_motion_ids(request):
    """Stitch two motion IDs directly without baking.

    Args:
        request: StitchMotionIdsRequest

    Returns:
        OperationResult
    """
    if not request.leading_motion_id.strip():
        return OperationResult(success=False, message="Leading Motion ID is required")
    if not request.trailing_motion_id.strip():
        return OperationResult(success=False, message="Trailing Motion ID is required")
    if request.duration <= 0:
        return OperationResult(success=False, message="Duration must be greater than 0")

    stitch_request = StitchRequest(
        domain=request.domain,
        api_key=request.api_key,
        character_id=request.character_id,
        leading_motion_id=request.leading_motion_id,
        trailing_motion_id=request.trailing_motion_id,
        duration=request.duration,
    )
    stitch_result = client.create_stitched_motion(stitch_request)

    if not stitch_result.success:
        return OperationResult(success=False, message=f"Stitch API failed: {stitch_result.message}")

    stitched_motion_id = stitch_result.data.get("motion_id")

    # Download and import
    import_result = download_and_import_motion(
        request.domain, request.api_key, request.character_id, stitched_motion_id
    )

    if import_result.success:
        return OperationResult(
            success=True,
            message=f"Motion IDs stitched and imported! ID: {stitched_motion_id}",
            data={
                "stitched_motion_id": stitched_motion_id,
                "leading_motion_id": request.leading_motion_id,
                "trailing_motion_id": request.trailing_motion_id,
            },
        )
    else:
        return OperationResult(
            success=True,
            message=f"Motion IDs stitched! ID: {stitched_motion_id}. "
            f"Import failed: {import_result.message}",
            data={"stitched_motion_id": stitched_motion_id},
        )
