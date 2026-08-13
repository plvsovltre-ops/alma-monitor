#!/usr/bin/env python3
"""Apply the reviewed ALMA field-mode safeguards to an existing QGIS project."""

import argparse
import json
import os
import shutil
import tempfile
import xml.etree.ElementTree as ET
import zipfile


PHOTO_EXPRESSION = (
    "'DCIM/alma_' || format_date(now(),'yyyyMMdd_HHmmsszzz') || '.{extension}'"
)


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


def configure_project_xml(xml_bytes):
    root = ET.fromstring(xml_bytes)
    photos = _layer(root, "photos")
    incidents = _layer(root, "Инцидент")

    _require_field(photos, "photo")
    _require_field(photos, "external_pk")
    _require_field(incidents, "incident_type")
    _require_field(incidents, "volunteer_email")

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
        configured_xml = configure_project_xml(source.read(qgs_name))
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
