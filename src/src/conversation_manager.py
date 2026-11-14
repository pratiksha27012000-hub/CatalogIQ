
import uuid
from datetime import datetime

from query_interpreter import (
    interpret_query,
    interpret_followup
)

from query_executor import (
    validate_query,
    safe_execute_query
)


class ConversationManager:

    def __init__(self, con, client):

        self.con = con
        self.client = client

        # Active conversations stored in memory
        self.sessions = {}


    def start_conversation(self, catalogue_id):

        conversation_id = str(uuid.uuid4())

        self.sessions[conversation_id] = {
            "conversation_id": conversation_id,
            "catalogue_id": catalogue_id,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "history": [],
            "previous_question": None,
            "previous_query_spec": None
        }

        return conversation_id


    def get_conversation(self, conversation_id):

        return self.sessions.get(conversation_id)


    def ask(self, conversation_id, question):

        session = self.sessions.get(conversation_id)

        if session is None:
            return {
                "status": "error",
                "errors": ["Conversation not found."]
            }

        catalogue_id = session["catalogue_id"]

        try:

            # First question in a conversation
            if session["previous_query_spec"] is None:

                query_spec = interpret_query(
                    self.client,
                    question
                )

            # Follow-up question
            else:

                query_spec = interpret_followup(
                    self.client,
                    session["previous_question"],
                    session["previous_query_spec"],
                    question
                )

            # Validate generated query
            validation = validate_query(query_spec)

            if not validation["valid"]:
                return {
                    "status": "error",
                    "stage": "validation",
                    "errors": validation["errors"],
                    "query_spec": query_spec
                }

            # Execute query against the selected catalogue
            result = safe_execute_query(
                self.con,
                query_spec,
                catalogue_id
            )

            if result["status"] != "success":
                return {
                    "status": "error",
                    "stage": "execution",
                    "errors": result.get("errors", ["Query execution failed."]),
                    "query_spec": query_spec
                }

            # Update session only after successful execution
            session["history"].append({
                "question": question,
                "query_spec": query_spec,
                "result_summary": {
                    "matching_records": result.get("matching_records"),
                    "displayed_records": result.get("displayed_records"),
                    "answer": result.get("answer")
                },
                "timestamp": datetime.now().isoformat()
            })

            session["previous_question"] = question
            session["previous_query_spec"] = query_spec
            session["updated_at"] = datetime.now().isoformat()

            return {
                "status": "success",
                "conversation_id": conversation_id,
                "catalogue_id": catalogue_id,
                "question": question,
                "query_spec": query_spec,
                "result": result
            }

        except Exception as e:

            return {
                "status": "error",
                "stage": "interpretation_or_execution",
                "errors": [str(e)]
            }


    def get_history(self, conversation_id):

        session = self.sessions.get(conversation_id)

        if session is None:
            return None

        return session["history"]


    def reset_conversation(self, conversation_id):

        session = self.sessions.get(conversation_id)

        if session is None:
            return {
                "status": "error",
                "errors": ["Conversation not found."]
            }

        session["history"] = []
        session["previous_question"] = None
        session["previous_query_spec"] = None
        session["updated_at"] = datetime.now().isoformat()

        return {
            "status": "success",
            "message": "Conversation context has been reset.",
            "conversation_id": conversation_id
        }


    def end_conversation(self, conversation_id):

        if conversation_id not in self.sessions:
            return {
                "status": "error",
                "errors": ["Conversation not found."]
            }

        del self.sessions[conversation_id]

        return {
            "status": "success",
            "message": "Conversation ended."
        }
