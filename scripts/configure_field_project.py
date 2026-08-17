#!/usr/bin/env python3
"""Apply the reviewed ALMA field-mode safeguards to an existing QGIS project."""

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import uuid
import xml.etree.ElementTree as ET
import zipfile


PHOTO_EXPRESSION = (
    "'DCIM/alma_' || format_date(now(),'yyyyMMdd_HHmmsszzz') || '.{extension}'"
)
EDITABLE_LAYER_NAMES = {"Инцидент", "photos"}


def _layer(root, name):
    matches = [
        item for item in root.findall(".//maplayer")
        if item.findtext("layername") == name
    ]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one QGIS layer named {name!r}")
    return matches[0]


def _option_map(layer):
    custom = layer.find("customproperties")
    if custom is None:
        custom = ET.SubElement(layer, "customproperties")
    option_map = custom.find("Option")
    if option_map is None:
        option_map = ET.SubElement(custom, "Option", {"type": "Map"})
    return option_map


def _set_option(option_map, name, value, value_type="QString"):
    option = next(
        (item for item in option_map.findall("Option") if item.get("name") == name),
        None,
    )
    if option is None:
        option = ET.SubElement(option_map, "Option")
    option.set("name", name)
    option.set("type", value_type)
    option.set("value", str(value))


def _require_field(layer, field_name):
    constraint = next(
        (
            item for item in layer.findall("./constraints/constraint")
            if item.get("field") == field_name
        ),
        None,
    )
    if constraint is None:
        raise ValueError(f"Missing QGIS constraint for field {field_name!r}")
    flags = int(constraint.get("constraints", "0")) | 1
    constraint.set("constraints", str(flags))
    constraint.set("notnull_strength", "1")


def _require_unique_field(layer, field_name):
    _require_field(layer, field_name)
    constraint = next(
        item for item in layer.findall("./constraints/constraint")
        if item.get("field") == field_name
    )
    flags = int(constraint.get("constraints", "0")) | 2
    constraint.set("constraints", str(flags))
    constraint.set("unique_strength", "1")


def _set_default(layer, field_name, expression):
    defaults = layer.find("defaults")
    if defaults is None:
        defaults = ET.SubElement(layer, "defaults")
    default = next(
        (
            item for item in defaults.findall("default")
            if item.get("field") == field_name
        ),
        None,
    )
    if default is None:
        default = ET.SubElement(defaults, "default", {"field": field_name})
    default.set("expression", expression)
    default.set("applyOnUpdate", "0")


def _local_gpkg_source(datasource):
    path, separator, options = (datasource or "").partition("|")
    if not path.lower().endswith(".gpkg"):
        return None
    return path, separator + options if separator else ""


def _root_source(datasource):
    parsed = _local_gpkg_source(datasource)
    if parsed is None:
        return datasource
    path, options = parsed
    return f"./{os.path.basename(path)}{options}"


def _configure_local_layers(root):
    tree_by_id = {
        item.get("id"): item
        for item in root.findall(".//layer-tree-layer")
        if item.get("id")
    }
    for layer in root.findall(".//maplayer"):
        datasource = layer.find("datasource")
        if datasource is None or not datasource.text:
            continue
        normalized = _root_source(datasource.text)
        datasource.text = normalized
        layer_id = layer.findtext("id")
        tree_item = tree_by_id.get(layer_id)
        if tree_item is not None:
            tree_item.set("source", normalized)

        if layer.get("type") == "vector" and layer.findtext("provider") == "ogr":
            layer_name = layer.findtext("layername")
            layer.set(
                "readOnly",
                "0" if layer_name in EDITABLE_LAYER_NAMES else "1",
            )
            if layer_name == "Инцидент" and tree_item is not None:
                tree_item.set("checked", "Qt::Checked")


def _configure_gps_target(root, incidents):
    gps = root.find("ProjectGpsSettings")
    if gps is None:
        gps = ET.SubElement(root, "ProjectGpsSettings")
    incident_id = incidents.findtext("id")
    if not incident_id:
        raise ValueError("The incident layer has no stable QGIS ID")
    gps.set("destinationLayer", incident_id)
    gps.set("destinationLayerProvider", "ogr")
    gps.set("destinationLayerSource", "./Инцидент.gpkg|layername=Инцидент")
    gps.set("destinationLayerName", "Инцидент")
    gps.set("destinationFollowsActiveLayer", "0")


def _clear_export_directory(root):
    properties = root.find("properties")
    if properties is None:
        properties = ET.SubElement(root, "properties")
    qfield_sync = properties.find("QFieldSync")
    if qfield_sync is None:
        qfield_sync = ET.SubElement(properties, "QFieldSync")
    export_directory = qfield_sync.find("exportDirectoryProject")
    if export_directory is None:
        export_directory = ET.SubElement(
            qfield_sync,
            "exportDirectoryProject",
            {"type": "QString"},
        )
    export_directory.set("type", "QString")
    export_directory.text = None


def _file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _materialize_root_sources(root, project_directory):
    """Copy local GeoPackages beside the QGZ without overwriting different data."""
    processed = set()
    for layer in root.findall(".//maplayer"):
        datasource = layer.findtext("datasource")
        parsed = _local_gpkg_source(datasource)
        if parsed is None:
            continue
        source_text, _ = parsed
        source_path = (
            source_text
            if os.path.isabs(source_text)
            else os.path.normpath(os.path.join(project_directory, source_text))
        )
        target_path = os.path.join(project_directory, os.path.basename(source_text))
        key = (os.path.realpath(source_path), os.path.realpath(target_path))
        if key in processed:
            continue
        processed.add(key)
        if not os.path.isfile(source_path):
            if os.path.isfile(target_path):
                continue
            raise ValueError(f"Missing GeoPackage referenced by QGIS: {source_text}")
        if os.path.realpath(source_path) == os.path.realpath(target_path):
            continue
        if os.path.exists(target_path):
            if _file_sha256(source_path) != _file_sha256(target_path):
                raise ValueError(
                    "Refusing to overwrite a different root GeoPackage: "
                    f"{os.path.basename(target_path)}"
                )
            continue
        shutil.copy2(source_path, target_path)


def _repair_incident_ids(project_directory):
    """Backfill legacy blank relation IDs without guessing photo relationships."""
    path = os.path.join(project_directory, "Инцидент.gpkg")
    if not os.path.isfile(path):
        raise ValueError("Missing GeoPackage referenced by QGIS: Инцидент.gpkg")

    connection = sqlite3.connect(path)
    try:
        # GDAL-created GeoPackages may evaluate this function in generic
        # RTree UPDATE triggers even when only a non-spatial field changes.
        # The migration never updates geometry or fid.
        connection.create_function(
            "ST_IsEmpty",
            1,
            lambda geometry: 1 if geometry is None else 0,
        )
        for function_name in ("ST_MinX", "ST_MaxX", "ST_MinY", "ST_MaxY"):
            connection.create_function(function_name, 1, lambda geometry: None)
        connection.execute("BEGIN IMMEDIATE")
        columns = {
            row[1] for row in connection.execute('PRAGMA table_info("Инцидент")')
        }
        if "fid" not in columns or "unique-id" not in columns:
            raise ValueError(
                "Incident GeoPackage must contain fid and unique-id fields"
            )
        duplicate = connection.execute(
            'SELECT "unique-id" FROM "Инцидент" '
            'WHERE "unique-id" IS NOT NULL AND TRIM("unique-id") <> \'\' '
            'GROUP BY "unique-id" HAVING COUNT(*) > 1 LIMIT 1'
        ).fetchone()
        if duplicate is not None:
            raise ValueError("Incident GeoPackage contains duplicate unique-id values")

        missing = [
            row[0]
            for row in connection.execute(
                'SELECT fid FROM "Инцидент" '
                'WHERE "unique-id" IS NULL OR TRIM("unique-id") = \'\''
            )
        ]
        for fid in missing:
            relation_id = "{" + str(uuid.uuid4()) + "}"
            connection.execute(
                'UPDATE "Инцидент" SET "unique-id" = ? WHERE fid = ?',
                (relation_id, fid),
            )
        connection.commit()
        return len(missing)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def configure_project_xml(xml_bytes):
    root = ET.fromstring(xml_bytes)
    photos = _layer(root, "photos")
    incidents = _layer(root, "Инцидент")

    _configure_local_layers(root)
    _configure_gps_target(root, incidents)
    _clear_export_directory(root)

    _require_field(photos, "photo")
    _require_field(photos, "external_pk")
    _require_field(incidents, "incident_type")
    _require_field(incidents, "volunteer_email")
    _require_unique_field(incidents, "unique-id")
    _set_default(incidents, "unique-id", "uuid()")

    relation_widget = next(
        (
            field for field in photos.findall("./fieldConfiguration/field")
            if field.get("name") == "external_pk"
        ),
        None,
    )
    if relation_widget is None:
        raise ValueError("Missing external_pk relation widget")
    for option in relation_widget.findall(".//Option"):
        if option.get("name") == "AllowNULL":
            option.set("type", "bool")
            option.set("value", "false")
        elif option.get("name") == "ReferencedLayerDataSource":
            option.set(
                "value",
                "./Инцидент.gpkg|layername=Инцидент",
            )

    naming = json.dumps({"photo": PHOTO_EXPRESSION}, ensure_ascii=False)
    options = _option_map(photos)
    _set_option(options, "QFieldSync/action", "copy")
    _set_option(options, "QFieldSync/cloud_action", "offline")
    _set_option(options, "QFieldSync/attachment_naming", naming)
    _set_option(options, "QFieldSync/photo_naming", naming)

    project_properties = root.find("properties")
    if project_properties is None:
        project_properties = ET.SubElement(root, "properties")
    mergin = project_properties.find("Mergin")
    if mergin is None:
        mergin = ET.SubElement(project_properties, "Mergin")
    photo_naming = mergin.find("PhotoNaming")
    if photo_naming is None:
        photo_naming = ET.SubElement(mergin, "PhotoNaming")
    layer_id = photos.findtext("id")
    if not layer_id:
        raise ValueError("The photos layer has no stable QGIS ID")
    layer_naming = photo_naming.find(layer_id)
    if layer_naming is None:
        layer_naming = ET.SubElement(photo_naming, layer_id)
    field_naming = layer_naming.find("photo")
    if field_naming is None:
        field_naming = ET.SubElement(layer_naming, "photo", {"type": "QString"})
    field_naming.set("type", "QString")
    field_naming.text = PHOTO_EXPRESSION

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def configure_qgz(path):
    path = os.path.abspath(path)
    with zipfile.ZipFile(path, "r") as source:
        names = source.namelist()
        qgs_names = [name for name in names if name.endswith(".qgs")]
        if len(qgs_names) != 1:
            raise ValueError("QGZ must contain exactly one QGS project")
        qgs_name = qgs_names[0]
        original_xml = source.read(qgs_name)
        _materialize_root_sources(
            ET.fromstring(original_xml),
            os.path.dirname(path),
        )
        configured_xml = configure_project_xml(original_xml)
        members = [(item, source.read(item.filename)) for item in source.infolist()]

    directory = os.path.dirname(path)
    with tempfile.NamedTemporaryFile(
        prefix="alma-field-",
        suffix=".qgz",
        dir=directory,
        delete=False,
    ) as temporary:
        temporary_path = temporary.name
    try:
        with zipfile.ZipFile(temporary_path, "w") as destination:
            for item, content in members:
                destination.writestr(
                    item,
                    configured_xml if item.filename == qgs_name else content,
                )
        shutil.copystat(path, temporary_path)
        _repair_incident_ids(directory)
        os.replace(temporary_path, path)
    finally:
        if os.path.exists(temporary_path):
            os.unlink(temporary_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("qgz", help="Path to the active ALMA QGIS project")
    args = parser.parse_args()
    configure_qgz(args.qgz)
    print(f"Configured ALMA field mode: {os.path.abspath(args.qgz)}")


if __name__ == "__main__":
    main()
