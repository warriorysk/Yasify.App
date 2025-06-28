
# import asyncio
# from fastapi import FastAPI, WebSocket, WebSocketDisconnect
# from fastapi.middleware.cors import CORSMiddleware
# import uvicorn
# from Backend.Model import FirstLayerDMM
# from Backend.Chatbot import ChatBot
# from Backend.RealTimeSearchEngine import RealtimeSearchEngine
# from Backend.ImageGeneration import generate_images_and_return_paths, image_to_base64

# app = FastAPI()

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# async def async_wrap_generator(sync_gen):
#     for item in sync_gen:
#         yield item
#         await asyncio.sleep(0)

# class WebSocketManager:
#     def __init__(self):
#         self.active_connections: list[WebSocket] = []

#     async def connect(self, websocket: WebSocket):
#         await websocket.accept()
#         self.active_connections.append(websocket)

#     def disconnect(self, websocket: WebSocket):
#         self.active_connections.remove(websocket)

#     async def send_json(self, websocket: WebSocket, message: dict):
#         await websocket.send_json(message)

# manager = WebSocketManager()

# @app.websocket("/ws")
# async def websocket_endpoint(websocket: WebSocket):
#     await manager.connect(websocket)
#     try:
#         while True:
#             user_msg = await websocket.receive_text()
#             task_types = list(FirstLayerDMM(prompt=user_msg))

#             for task in task_types:
#                 if task.startswith("general"):
#                     async for chunk in async_wrap_generator(ChatBot(user_msg)):
#                         await manager.send_json(websocket, {"general": chunk})

#                 elif task.startswith("realtime"):
#                     async for chunk in async_wrap_generator(RealtimeSearchEngine(user_msg)):
#                         await manager.send_json(websocket, {"realtime": chunk})

#                 elif task.startswith("generate image"):
#                     prompt = task.replace("generate image", "").strip()
#                     await manager.send_json(websocket, {"status": f"Generating images for '{prompt}'..."})
#                     image_paths = await generate_images_and_return_paths(prompt)
#                     for path in image_paths:
#                         image_b64 = image_to_base64(path)
#                         await manager.send_json(websocket, {
#                             "image": image_b64,
#                             "filename": os.path.basename(path)
#                         })

#                 else:
#                     await manager.send_json(websocket, {task: f"Handler for '{task}' not implemented."})

#     except WebSocketDisconnect:
#         manager.disconnect(websocket)
#         print("Client disconnected")

# if __name__ == "__main__":
#     uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
import asyncio
import os
import secrets
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from dotenv import dotenv_values

from Backend.Model import FirstLayerDMM
from Backend.Chatbot import ChatBot
from Backend.RealTimeSearchEngine import RealtimeSearchEngine
from Backend.ImageGeneration import generate_images_and_return_paths, image_to_base64

# Load env
env = dotenv_values(".env")
EXPECTED_BEARER = env.get("WEBSOCKET_BEARER_TOKEN")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def async_wrap_generator(sync_gen):
    for item in sync_gen:
        yield item
        await asyncio.sleep(0)

class WebSocketManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.sessions: dict[str, dict] = {}  # sessionID -> session data

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_json(self, websocket: WebSocket, message: dict):
        await websocket.send_json(message)

    def create_session(self):
        session_id = secrets.token_hex(8)
        self.sessions[session_id] = {
            "queries": []
        }
        return session_id

    def session_exists(self, session_id: str):
        return session_id in self.sessions

    def add_query(self, session_id: str, query: str):
        self.sessions[session_id]["queries"].append(query)

manager = WebSocketManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # Validate Bearer token
    token = websocket.query_params.get("token")
    # if token != EXPECTED_BEARER:
    #     await websocket.close(code=1008)
    #     print("Unauthorized connection attempt.")
    #     return

    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()

            event_type = data.get("event_type")
            version = data.get("version")
            device_type = data.get("device_type")
            device_details = data.get("device_details")
            session_id = data.get("sessionID")

            if event_type == "Create_session":
                if not session_id:
                    # Create new session
                    session_id = manager.create_session()
                    await manager.send_json(websocket, {
                        "success": True,
                        "sessionID": session_id,
                        "message": "Session created successfully"
                    })
                else:
                    # Resume existing session if valid
                    if manager.session_exists(session_id):
                        await manager.send_json(websocket, {
                            "success": True,
                            "sessionID": session_id,
                            "message": "Resumed existing session"
                        })
                    else:
                        await manager.send_json(websocket, {
                            "success": False,
                            "message": "Invalid session ID"
                        })

            elif event_type == "Get_Response":
                query = data.get("query")
                if not session_id or not manager.session_exists(session_id):
                    await manager.send_json(websocket, {
                        "success": False,
                        "message": "Session ID missing or invalid"
                    })
                    continue

                manager.add_query(session_id, query)

                task_types = list(FirstLayerDMM(prompt=query))

                for task in task_types:
                    if task.startswith("general"):
                        async for chunk in async_wrap_generator(ChatBot(query)):
                            await manager.send_json(websocket, {
                                "success": True,
                                "sessionID": session_id,
                                "type": "general",
                                "data": chunk
                            })

                    elif task.startswith("realtime"):
                        async for chunk in async_wrap_generator(RealtimeSearchEngine(query)):
                            await manager.send_json(websocket, {
                                "success": True,
                                "sessionID": session_id,
                                "type": "realtime",
                                "data": chunk
                            })

                    elif task.startswith("generate image"):
                        prompt = task.replace("generate image", "").strip()
                        await manager.send_json(websocket, {
                            "success": True,
                            "sessionID": session_id,
                            "status": f"Generating images for '{prompt}'..."
                        })
                        image_paths = await generate_images_and_return_paths(prompt)
                        for path in image_paths:
                            image_b64 = image_to_base64(path)
                            await manager.send_json(websocket, {
                                "success": True,
                                "sessionID": session_id,
                                "type": "image",
                                "filename": os.path.basename(path),
                                "image": image_b64
                            })

                    else:
                        await manager.send_json(websocket, {
                            "success": False,
                            "sessionID": session_id,
                            "message": f"Handler for '{task}' not implemented."
                        })

            else:
                await manager.send_json(websocket, {
                    "success": False,
                    "message": "Invalid event_type"
                })

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print("Client disconnected")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
