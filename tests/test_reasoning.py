from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, XSD

from etl.reasoning import apply_partial_delivery_reasoning


O2C = Namespace("http://enterprise.com/ontology/o2c#")


def test_partial_delivery_anomaly_is_inferred_from_delivery_sum() -> None:
    graph = Graph()
    sales_item = URIRef("http://enterprise.com/resource/sales-item/1-10")
    delivery_item = URIRef("http://enterprise.com/resource/delivery-item/8-10")

    graph.add((sales_item, RDF.type, O2C.SalesItem))
    graph.add((sales_item, O2C.orderedQuantity, Literal("10", datatype=XSD.decimal)))
    graph.add((sales_item, O2C.fulfilledByDeliveryItem, delivery_item))
    graph.add((delivery_item, RDF.type, O2C.DeliveryItem))
    graph.add((delivery_item, O2C.deliveredQuantity, Literal("4", datatype=XSD.decimal)))

    apply_partial_delivery_reasoning(graph)

    assert (sales_item, RDF.type, O2C.PartialDeliveryAnomaly) in graph


def test_fully_delivered_sales_item_is_not_marked_anomalous() -> None:
    graph = Graph()
    sales_item = URIRef("http://enterprise.com/resource/sales-item/2-10")
    delivery_item = URIRef("http://enterprise.com/resource/delivery-item/9-10")

    graph.add((sales_item, RDF.type, O2C.SalesItem))
    graph.add((sales_item, O2C.orderedQuantity, Literal("10", datatype=XSD.decimal)))
    graph.add((sales_item, O2C.fulfilledByDeliveryItem, delivery_item))
    graph.add((delivery_item, RDF.type, O2C.DeliveryItem))
    graph.add((delivery_item, O2C.deliveredQuantity, Literal("10", datatype=XSD.decimal)))

    apply_partial_delivery_reasoning(graph)

    assert (sales_item, RDF.type, O2C.PartialDeliveryAnomaly) not in graph


def test_sales_item_without_delivery_is_marked_anomalous() -> None:
    graph = Graph()
    sales_item = URIRef("http://enterprise.com/resource/sales-item/3-10")

    graph.add((sales_item, RDF.type, O2C.SalesItem))
    graph.add((sales_item, O2C.orderedQuantity, Literal("5", datatype=XSD.decimal)))

    apply_partial_delivery_reasoning(graph)

    assert (sales_item, RDF.type, O2C.PartialDeliveryAnomaly) in graph
