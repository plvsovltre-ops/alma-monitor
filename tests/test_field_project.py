import json
import unittest
import xml.etree.ElementTree as ET

from scripts.configure_field_project import PHOTO_EXPRESSION, configure_project_xml


def _layer(name, layer_id, fields):
    layer = ET.Element("maplayer")
    ET.SubElement(layer, "id").text = layer_id
    ET.SubElement(layer, "layername").text = name
    configuration = ET.SubElement(layer, "fieldConfiguration")
    constraints = ET.SubElement(layer, "constraints")
    custom = ET.SubElement(layer, "customproperties")
    ET.SubElement(custom, "Option", {"type": "Map"})
    for field_name in fields:
        field = ET.SubElement(configuration, "field", {"name": field_name})
        widget = ET.SubElement(field, "editWidget", {"type": "TextEdit"})
        config = ET.SubElement(widget, "config")
        ET.SubElement(config, "Option", {"type": "Map"})
        ET.SubElement(
            constraints,
            "constraint",
            {
                "field": field_name,
                "constraints": "0",
                "notnull_strength": "0",
                "unique_strength": "0",
                "exp_strength": "0",
            },
        )
    return layer


def _project_xml():
    root = ET.Element("qgis")
    layers = ET.SubElement(root, "projectlayers")
    photos = _layer("photos", "photos_id", ["photo", "external_pk"])
    external = next(
        field for field in photos.findall("./fieldConfiguration/field")
        if field.get("name") == "external_pk"
    )
    external.find("editWidget").set("type", "RelationReference")
    option_map = external.find("./editWidget/config/Option")
    ET.SubElement(
        option_map,
        "Option",
        {"name": "AllowNULL", "type": "bool", "value": "true"},
    )
    ET.SubElement(
        option_map,
        "Option",
        {
            "name": "ReferencedLayerDataSource",
            "type": "QString",
            "value": "/private/old/Инцидент.gpkg|layername=Инцидент",
        },
    )
    layers.append(photos)
    layers.append(_layer("Инцидент", "incident_id", ["incident_type"]))
    return ET.tostring(root, encoding="utf-8")


class FieldProjectTests(unittest.TestCase):
    def test_configures_required_fields_and_attachment_naming(self):
        root = ET.fromstring(configure_project_xml(_project_xml()))
        photos = next(
            layer for layer in root.findall(".//maplayer")
            if layer.findtext("layername") == "photos"
        )
        incidents = next(
            layer for layer in root.findall(".//maplayer")
            if layer.findtext("layername") == "Инцидент"
        )

        for layer, field_name in (
            (photos, "photo"),
            (photos, "external_pk"),
            (incidents, "incident_type"),
        ):
            constraint = next(
                item for item in layer.findall("./constraints/constraint")
                if item.get("field") == field_name
            )
            self.assertEqual("1", constraint.get("constraints"))
            self.assertEqual("1", constraint.get("notnull_strength"))

        options = {
            item.get("name"): item.get("value")
            for item in photos.findall("./customproperties/Option/Option")
        }
        self.assertEqual(
            {"photo": PHOTO_EXPRESSION},
            json.loads(options["QFieldSync/attachment_naming"]),
        )
        self.assertEqual(
            PHOTO_EXPRESSION,
            root.findtext("./properties/Mergin/PhotoNaming/photos_id/photo"),
        )

    def test_rejects_project_without_expected_layer(self):
        root = ET.fromstring(_project_xml())
        layers = root.find("projectlayers")
        for layer in list(layers):
            if layer.findtext("layername") == "photos":
                layers.remove(layer)
        with self.assertRaisesRegex(ValueError, "photos"):
            configure_project_xml(ET.tostring(root, encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
