from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from falkordb import FalkorDB
except ImportError:
    FalkorDB = None

from .schema import (
    FactSource,
    GuidanceAssessment,
    LifestyleChange,
    MedicalFact,
    Patient,
    SymptomEvent,
    TemporalRelation,
)


class MediGraphStore:
    """
    FalkorDB-powered graph memory engine with a persistent local fallback.
    Demonstrates FalkorDB Cypher queries, temporal relationship edges,
    and multi-agent graph traversal.
    """

    def __init__(
        self,
        graph_name: str = "medimemory",
        host: str = "localhost",
        port: int = 6379,
        storage_file: Optional[str] = None,
    ):
        self.graph_name = graph_name
        self.host = os.getenv("FALKORDB_HOST", host)
        self.port = int(os.getenv("FALKORDB_PORT", str(port)))
        self.storage_file = storage_file or os.path.join(
            os.path.dirname(__file__), "..", "data", "graph_persistence.json"
        )
        self._mode = "local"
        self._connection_error: Optional[str] = None
        self._db: Any = None
        self._graph: Any = None

        # Local fallback in-memory store
        self._nodes: Dict[str, Dict[str, Any]] = {}
        self._edges: List[Dict[str, Any]] = []

        self._load_local_storage()
        self._connect_falkordb()

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def connection_error(self) -> Optional[str]:
        return self._connection_error

    def _connect_falkordb(self) -> None:
        """Attempts connection to active FalkorDB instance."""
        if FalkorDB is None:
            self._mode = "local"
            return

        try:
            self._db = FalkorDB(host=self.host, port=self.port)
            # Ping by selecting graph
            self._graph = self._db.select_graph(self.graph_name)
            # Run simple test query
            self._graph.query("RETURN 1")
            self._mode = "falkordb"
            self._sync_to_falkordb()
        except Exception as exc:
            self._connection_error = str(exc)
            self._mode = "local"

    def _save_local_storage(self) -> None:
        """Persists local graph state so memory survives application restarts."""
        try:
            path = Path(self.storage_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"nodes": self._nodes, "edges": self._edges}, f, indent=2)
        except Exception:
            pass

    def _load_local_storage(self) -> None:
        """Loads persisted graph state from previous sessions."""
        try:
            path = Path(self.storage_file)
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._nodes = data.get("nodes", {})
                    self._edges = data.get("edges", [])
        except Exception:
            self._nodes = {}
            self._edges = []

    def _sync_to_falkordb(self) -> None:
        """When FalkorDB is available, ensures schema indices exist."""
        if self._mode != "falkordb" or not self._graph:
            return
        try:
            self._graph.query("CREATE INDEX FOR (p:Patient) ON (p.id)")
            self._graph.query("CREATE INDEX FOR (s:SymptomEvent) ON (s.id)")
            self._graph.query("CREATE INDEX FOR (l:LifestyleChange) ON (l.id)")
        except Exception:
            pass

    # ------------------ PATIENT PROFILE ------------------

    def save_patient(self, patient: Patient) -> None:
        props = patient.model_dump()
        node_id = f"patient_{patient.id}"
        self._nodes[node_id] = {
            "id": node_id,
            "label": "Patient",
            "name": patient.name,
            "properties": props,
        }

        if self._mode == "falkordb" and self._graph:
            query = """
            MERGE (p:Patient {id: $id})
            SET p.name = $name,
                p.age = $age,
                p.gender = $gender,
                p.allergies = $allergies,
                p.conditions = $conditions
            """
            params = {
                "id": patient.id,
                "name": patient.name,
                "age": patient.age,
                "gender": patient.gender,
                "allergies": json.dumps(patient.allergies),
                "conditions": json.dumps(patient.existing_conditions),
            }
            try:
                self._graph.query(query, params=params)
            except Exception:
                pass

        self._save_local_storage()

    def get_patient(self, patient_id: str) -> Optional[Patient]:
        node_id = f"patient_{patient_id}"
        if node_id in self._nodes:
            props = self._nodes[node_id].get("properties", {})
            return Patient(**props)
        return None

    # ------------------ LIFESTYLE CHANGE ------------------

    def save_lifestyle_change(self, lifestyle: LifestyleChange) -> None:
        node_id = f"lifestyle_{lifestyle.id}"
        self._nodes[node_id] = {
            "id": node_id,
            "label": "LifestyleChange",
            "name": lifestyle.name,
            "properties": lifestyle.model_dump(),
        }

        # Edge from Patient to LifestyleChange
        patient_node_id = f"patient_{lifestyle.patient_id}"
        edge = {
            "from": patient_node_id,
            "to": node_id,
            "relationship": "REPORTED",
            "properties": {"source": lifestyle.source.value, "date": lifestyle.start_date},
        }
        if not any(e["from"] == edge["from"] and e["to"] == edge["to"] and e["relationship"] == edge["relationship"] for e in self._edges):
            self._edges.append(edge)

        if self._mode == "falkordb" and self._graph:
            query = """
            MERGE (p:Patient {id: $patient_id})
            MERGE (l:LifestyleChange {id: $id})
            SET l.name = $name,
                l.change_type = $change_type,
                l.start_date = $start_date,
                l.details = $details,
                l.source = $source
            MERGE (p)-[r:REPORTED]->(l)
            SET r.recorded_at = $created_at
            """
            params = {
                "patient_id": lifestyle.patient_id,
                "id": lifestyle.id,
                "name": lifestyle.name,
                "change_type": lifestyle.change_type,
                "start_date": lifestyle.start_date,
                "details": lifestyle.details,
                "source": lifestyle.source.value,
                "created_at": lifestyle.created_at,
            }
            try:
                self._graph.query(query, params=params)
            except Exception:
                pass

        self._save_local_storage()

    # ------------------ SYMPTOM EVENT ------------------

    def save_symptom_event(self, symptom: SymptomEvent) -> None:
        node_id = f"symptom_{symptom.id}"
        self._nodes[node_id] = {
            "id": node_id,
            "label": "SymptomEvent",
            "name": symptom.name,
            "properties": symptom.model_dump(),
        }

        patient_node_id = f"patient_{symptom.patient_id}"
        edge = {
            "from": patient_node_id,
            "to": node_id,
            "relationship": "EXPERIENCES",
            "properties": {
                "source": symptom.source.value,
                "reported_date": symptom.reported_date,
                "severity": symptom.severity,
            },
        }
        if not any(e["from"] == edge["from"] and e["to"] == edge["to"] and e["relationship"] == edge["relationship"] for e in self._edges):
            self._edges.append(edge)

        if self._mode == "falkordb" and self._graph:
            query = """
            MERGE (p:Patient {id: $patient_id})
            MERGE (s:SymptomEvent {id: $id})
            SET s.name = $name,
                s.severity = $severity,
                s.reported_date = $reported_date,
                s.onset = $onset,
                s.duration = $duration,
                s.source = $source
            MERGE (p)-[r:EXPERIENCES]->(s)
            SET r.reported_at = $created_at
            """
            params = {
                "patient_id": symptom.patient_id,
                "id": symptom.id,
                "name": symptom.name,
                "severity": symptom.severity,
                "reported_date": symptom.reported_date,
                "onset": symptom.onset,
                "duration": symptom.duration,
                "source": symptom.source.value,
                "created_at": symptom.created_at,
            }
            try:
                self._graph.query(query, params=params)
            except Exception:
                pass

        self._save_local_storage()

    # ------------------ TEMPORAL RELATION ------------------

    def create_temporal_relation(self, relation: TemporalRelation) -> None:
        from_id = relation.from_node_id if relation.from_node_id.startswith(("lifestyle_", "symptom_")) else f"lifestyle_{relation.from_node_id}"
        to_id = relation.to_node_id if relation.to_node_id.startswith(("symptom_", "lifestyle_")) else f"symptom_{relation.to_node_id}"

        edge = {
            "from": from_id,
            "to": to_id,
            "relationship": "TEMPORALLY_RELATED_TO",
            "properties": {
                "days_apart": relation.days_apart,
                "relationship_type": relation.relationship_type,
                "explanation": relation.explanation,
                "causal_assumption": False,
            },
        }
        if not any(e["from"] == edge["from"] and e["to"] == edge["to"] and e["relationship"] == edge["relationship"] for e in self._edges):
            self._edges.append(edge)

        if self._mode == "falkordb" and self._graph:
            query = """
            MATCH (l {id: $from_id}), (s {id: $to_id})
            MERGE (l)-[r:TEMPORALLY_RELATED_TO]->(s)
            SET r.days_apart = $days_apart,
                r.relationship_type = $rel_type,
                r.explanation = $explanation,
                r.causal_assumption = false
            """
            params = {
                "from_id": relation.from_node_id.replace("lifestyle_", ""),
                "to_id": relation.to_node_id.replace("symptom_", ""),
                "days_apart": relation.days_apart,
                "rel_type": relation.relationship_type,
                "explanation": relation.explanation,
            }
            try:
                self._graph.query(query, params=params)
            except Exception:
                pass

        self._save_local_storage()

    # ------------------ GUIDANCE ASSESSMENT & MEDICAL FACTS ------------------

    def save_guidance_assessment(
        self,
        assessment: GuidanceAssessment,
        grounded_facts: List[MedicalFact],
    ) -> None:
        node_id = f"assessment_{assessment.id}"
        self._nodes[node_id] = {
            "id": node_id,
            "label": "GuidanceAssessment",
            "name": f"Assessment ({assessment.session_id})",
            "properties": assessment.model_dump(),
        }

        # Link from patient symptoms to assessment
        patient_node_id = f"patient_{assessment.patient_id}"
        symptom_nodes = [
            nid for nid, n in self._nodes.items()
            if n["label"] == "SymptomEvent" and n.get("properties", {}).get("patient_id") == assessment.patient_id
        ]
        for s_nid in symptom_nodes:
            self._edges.append({
                "from": s_nid,
                "to": node_id,
                "relationship": "ASSESSED_USING",
                "properties": {"session_id": assessment.session_id, "safety": assessment.safety_level.value},
            })

        # Grounding in medical facts
        for fact in grounded_facts:
            f_nid = f"medical_fact_{fact.id}"
            if f_nid not in self._nodes:
                self._nodes[f_nid] = {
                    "id": f_nid,
                    "label": "MedicalFact",
                    "name": fact.title,
                    "properties": fact.model_dump(),
                }
            self._edges.append({
                "from": node_id,
                "to": f_nid,
                "relationship": "GROUNDED_IN",
                "properties": {"citation": fact.citation},
            })

        self._save_local_storage()

    # ------------------ QUERIES & RETRIEVAL ------------------

    def get_patient_history(self, patient_id: str) -> Dict[str, Any]:
        """Retrieves complete timeline of patient reports, lifestyle changes, and symptoms."""
        lifestyles = []
        symptoms = []
        assessments = []

        for node in self._nodes.values():
            props = node.get("properties", {})
            if props.get("patient_id") == patient_id:
                if node["label"] == "LifestyleChange":
                    lifestyles.append(props)
                elif node["label"] == "SymptomEvent":
                    symptoms.append(props)
                elif node["label"] == "GuidanceAssessment":
                    assessments.append(props)

        # Sort by date
        lifestyles.sort(key=lambda x: x.get("start_date", ""), reverse=False)
        symptoms.sort(key=lambda x: x.get("reported_date", ""), reverse=False)

        return {
            "patient_id": patient_id,
            "lifestyles": lifestyles,
            "symptoms": symptoms,
            "assessments": assessments,
        }

    def get_temporally_related_events(self, patient_id: str) -> List[Dict[str, Any]]:
        """Retrieves all temporal relationship edges."""
        results = []
        for edge in self._edges:
            if edge.get("relationship") == "TEMPORALLY_RELATED_TO":
                from_node = self._nodes.get(edge["from"])
                to_node = self._nodes.get(edge["to"])
                results.append({
                    "from_node": from_node,
                    "to_node": to_node,
                    "properties": edge.get("properties", {}),
                })
        return results

    def export_graph_visualization(self, patient_id: str) -> Dict[str, Any]:
        """
        Exports the patient graph into nodes and links format for D3 / Vis-network.
        Color codes node types (Patient, LifestyleChange, SymptomEvent, MedicalFact, GuidanceAssessment).
        """
        type_colors = {
            "Patient": "#3B82F6",             # Blue
            "LifestyleChange": "#10B981",     # Emerald
            "SymptomEvent": "#F59E0B",        # Amber
            "MedicalFact": "#8B5CF6",         # Purple
            "GuidanceAssessment": "#EC4899",   # Pink
        }

        nodes = []
        for nid, n in self._nodes.items():
            props = n.get("properties", {})
            # Include nodes belonging to this patient or global medical facts
            if props.get("patient_id") == patient_id or n["label"] == "MedicalFact" or nid == f"patient_{patient_id}":
                nodes.append({
                    "id": nid,
                    "label": n.get("name", nid),
                    "type": n.get("label", "Node"),
                    "color": type_colors.get(n.get("label"), "#6B7280"),
                    "properties": props,
                })

        node_ids = {n["id"] for n in nodes}
        links = []
        for e in self._edges:
            if e["from"] in node_ids and e["to"] in node_ids:
                links.append({
                    "source": e["from"],
                    "target": e["to"],
                    "label": e.get("relationship", "RELATED_TO"),
                    "properties": e.get("properties", {}),
                })

        return {"nodes": nodes, "links": links, "mode": self._mode}

    def reset_patient(self, patient_id: str) -> None:
        """Resets nodes and edges for the given patient."""
        nodes_to_del = [
            nid for nid, n in self._nodes.items()
            if n.get("properties", {}).get("patient_id") == patient_id or nid == f"patient_{patient_id}"
        ]
        for nid in nodes_to_del:
            del self._nodes[nid]

        self._edges = [
            e for e in self._edges
            if e["from"] not in nodes_to_del and e["to"] not in nodes_to_del
        ]

        if self._mode == "falkordb" and self._graph:
            try:
                self._graph.query(
                    "MATCH (p:Patient {id: $id})-[*0..2]-(n) DETACH DELETE p, n",
                    params={"id": patient_id},
                )
            except Exception:
                pass

        self._save_local_storage()
