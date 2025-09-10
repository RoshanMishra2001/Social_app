from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import Optional
import os
import uuid
from datetime import datetime
from pathlib import Path

app = FastAPI()

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# In-memory storage (replace with database in production)
users_db = {}
posts_db = []


class User:
    def __init__(self, username: str, profile_picture: str = None):
        self.username = username
        self.profile_picture = profile_picture


# Sample user for demonstration
current_user = User(username="demo_user", profile_picture="https://via.placeholder.com/32")


@app.get("/create", response_class=HTMLResponse)
async def create_post_page(request: Request):
    """Render the create post page"""
    return templates.TemplateResponse("create_post.html", {
        "request": request,
        "user": current_user
    })


@app.post("/api/posts", response_class=HTMLResponse)
async def create_post(
        request: Request,
        title: str = Form(...),
        content: str = Form(...),
        image: Optional[UploadFile] = File(None),
        video: Optional[UploadFile] = File(None),
        db: Session = Depends(get_db)
):

    user = await get_current_user()
    """
    Handle post creation with file uploads
    """
    try:
        # Validate file types and sizes
        if image:
            if image.content_type not in ["image/jpeg", "image/png", "image/gif"]:
                raise HTTPException(status_code=400, detail="Invalid image format")
            if image.size > 5 * 1024 * 1024:  # 5MB limit
                raise HTTPException(status_code=400, detail="Image too large (max 5MB)")

        if video:
            if video.content_type not in ["video/mp4", "video/quicktime"]:
                raise HTTPException(status_code=400, detail="Invalid video format")
            if video.size > 50 * 1024 * 1024:  # 50MB limit
                raise HTTPException(status_code=400, detail="Video too large (max 50MB)")

        # Save uploaded files
        image_url = None
        video_url = None

        if image:
            image_filename = f"{uuid.uuid4()}_{image.filename}"
            image_path = Path("static/uploads/images") / image_filename
            image_path.parent.mkdir(parents=True, exist_ok=True)

            with open(image_path, "wb") as buffer:
                content = await image.read()
                buffer.write(content)

            image_url = f"/static/uploads/images/{image_filename}"

        if video:
            video_filename = f"{uuid.uuid4()}_{video.filename}"
            video_path = Path("static/uploads/videos") / video_filename
            video_path.parent.mkdir(parents=True, exist_ok=True)

            with open(video_path, "wb") as buffer:
                content = await video.read()
                buffer.write(content)

            video_url = f"/static/uploads/videos/{video_filename}"

        # Create post object
        post = {
            "id": str(uuid.uuid4()),
            "title": title,
            "content": content,
            "image_url": image_url,
            "video_url": video_url,
            "author": current_user.username,
            "author_profile_picture": current_user.profile_picture,
            "created_at": datetime.now().isoformat(),
            "likes": 0,
            "comments": []
        }

        # Save post (in production, use a database)
        posts_db.append(post)

        # Redirect to home page after successful post creation
        return RedirectResponse(url="/", status_code=303)

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating post: {str(e)}")


# Additional routes needed for the template
@app.get("/", response_class=HTMLResponse)
async def home_page(request: Request):
    """Home page route"""
    return templates.TemplateResponse("home.html", {
        "request": request,
        "user": current_user,
        "posts": posts_db
    })


@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    """Profile page route"""
    return templates.TemplateResponse("profile.html", {
        "request": request,
        "user": current_user
    })


@app.get("/logout")
async def logout():
    """Logout route"""
    # In a real application, you'd clear the session/token
    return RedirectResponse(url="/")


# Create necessary directories
def create_directories():
    Path("static/uploads/images").mkdir(parents=True, exist_ok=True)
    Path("static/uploads/videos").mkdir(parents=True, exist_ok=True)


@app.on_event("startup")
async def startup_event():
    create_directories()
