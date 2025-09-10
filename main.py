from fastapi import FastAPI, Depends, HTTPException, Request, Form, status, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from typing import Optional, List
from datetime import datetime
from jose import JWTError, jwt
import os
import shutil
import traceback
from database import SessionLocal, engine, get_db
import models

# Import routers first to avoid circular imports
from login import router as login_router
from signup import router as signup_router

# Then create all tables
try:
    print("Creating database tables...")
    models.Base.metadata.create_all(bind=engine)
    print("Database tables created successfully")
except Exception as e:
    print(f"Error creating database tables: {str(e)}")
    print(traceback.format_exc())

app = FastAPI(title="Social App API")


# Add error handling middleware with recursion protection
@app.middleware("http")
async def catch_exceptions_middleware(request: Request, call_next):
    try:
        # Add a recursion check
        if hasattr(request.state, 'recursion_depth'):
            if request.state.recursion_depth > 10:
                return JSONResponse(
                    status_code=500,
                    content={"detail": "Recursion limit exceeded"}
                )
            request.state.recursion_depth += 1
        else:
            request.state.recursion_depth = 1

        print(f"Request: {request.method} {request.url}")
        return await call_next(request)
    except Exception as e:
        print(f"Exception occurred: {str(e)}")
        print(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "error": str(e)}
        )


# Include routers
app.include_router(login_router, prefix="", tags=["auth"])
app.include_router(signup_router, prefix="", tags=["auth"])

# Create upload directories if they don't exist
try:
    print("Creating upload directories...")
    os.makedirs("static/uploads/profile_pictures", exist_ok=True)
    os.makedirs("static/uploads/posts", exist_ok=True)
    os.makedirs("static/uploads/groups", exist_ok=True)
    print("Upload directories created successfully")
except Exception as e:
    print(f"Error creating directories: {e}")
    print(traceback.format_exc())

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Constants for JWT
SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM = "HS256"


# Define get_user function locally to avoid circular imports
def get_user(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()


async def get_current_user(request: Request, db: Session = Depends(get_db)):
    try:
        print("get_current_user called")
        token = request.cookies.get("access_token")
        print(f"Token: {token}")

        if not token:
            print("No token found")
            return None

        try:
            if token.startswith("Bearer "):
                token = token[7:]

            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("sub")
            if username is None:
                print("No username in token payload")
                return None

            print(f"Username from token: {username}")
        except JWTError as e:
            print(f"JWT Error: {str(e)}")
            return None

        user = get_user(db, username)
        if user:
            print(f"User found: {user.username}")
        else:
            print("User not found in database")

        return user

    except Exception as e:
        print(f"Error in get_current_user: {str(e)}")
        print(traceback.format_exc())
        return None


# Theme management
@app.post("/api/theme")
async def set_theme(request: Request, theme: str = Form(...)):
    try:
        print(f"Setting theme to: {theme}")
        response = RedirectResponse(url=request.headers.get('referer', '/'), status_code=303)
        response.set_cookie(key="theme", value=theme, max_age=365 * 24 * 60 * 60)
        return response
    except Exception as e:
        print(f"Error in set_theme: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Error setting theme")


# Home page
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, db: Session = Depends(get_db)):
    try:
        print("Home page requested")
        user = await get_current_user(request, db)
        if not user:
            print("User not authenticated, redirecting to login")
            return RedirectResponse(url="/login", status_code=303)

        theme = request.cookies.get("theme", "light")
        print(f"Theme: {theme}")

        posts = db.query(models.Post).options(
            joinedload(models.Post.owner),
            joinedload(models.Post.likes)
        ).order_by(models.Post.created_at.desc()).all()

        suggestions = db.query(models.User).filter(
            models.User.id != user.id
        ).limit(5).all()

        group_suggestions = db.query(models.Group).options(
            joinedload(models.Group.members)
        ).limit(3).all()

        print(f"Found {len(posts)} posts, {len(suggestions)} suggestions, {len(group_suggestions)} group suggestions")

        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "user": user,
                "posts": posts,
                "suggestions": suggestions,
                "group_suggestions": group_suggestions,
                "theme": theme
            }
        )

    except Exception as e:
        print(f"Error in read_root: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Error loading home page")


# Profile page
@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, db: Session = Depends(get_db)):
    try:
        print("Profile page requested")
        user = await get_current_user(request, db)
        if not user:
            print("User not authenticated, redirecting to login")
            return RedirectResponse(url="/login", status_code=303)

        theme = request.cookies.get("theme", "light")

        # Get user's posts
        user_posts = db.query(models.Post).options(
            joinedload(models.Post.likes),
            joinedload(models.Post.comments)
        ).filter(models.Post.owner_id == user.id).order_by(
            models.Post.created_at.desc()
        ).all()

        # Get follower and following counts
        follower_count = db.query(models.Follow).filter(models.Follow.following_id == user.id).count()
        following_count = db.query(models.Follow).filter(models.Follow.follower_id == user.id).count()

        print(f"Profile loaded: {len(user_posts)} posts, {follower_count} followers, {following_count} following")

        return templates.TemplateResponse(
            "profile.html",
            {
                "request": request,
                "user": user,
                "posts": user_posts,
                "follower_count": follower_count,
                "following_count": following_count,
                "theme": theme
            }
        )

    except Exception as e:
        print(f"Error in profile_page: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Error loading profile")


# Update profile picture
@app.post("/api/profile/picture")
async def update_profile_picture(
        request: Request,
        profile_picture: UploadFile = File(...),
        db: Session = Depends(get_db)
):
    try:
        print("Updating profile picture")
        user = await get_current_user(request, db)
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")

        # Validate file type
        if not profile_picture.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="Only image files are allowed")

        # Save the uploaded file
        file_extension = profile_picture.filename.split(".")[-1]
        filename = f"profile_{user.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.{file_extension}"
        file_path = f"static/uploads/profile_pictures/{filename}"

        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        with open(file_path, "wb") as buffer:
            content = await profile_picture.read()
            buffer.write(content)

        profile_picture_url = f"/static/uploads/profile_pictures/{filename}"

        # Update user profile picture
        user.profile_picture = profile_picture_url
        db.commit()

        print(f"Profile picture updated: {profile_picture_url}")

        return RedirectResponse(url="/profile", status_code=303)

    except Exception as e:
        print(f"Error in update_profile_picture: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Error updating profile picture")


# Groups page
@app.get("/groups", response_class=HTMLResponse)
async def groups_page(request: Request, db: Session = Depends(get_db)):
    try:
        print("Groups page requested")
        user = await get_current_user(request, db)
        if not user:
            return RedirectResponse(url="/login", status_code=303)

        theme = request.cookies.get("theme", "light")

        # Get all groups with member count
        all_groups = db.query(models.Group).options(
            joinedload(models.Group.members)
        ).all()

        # Get user's groups
        user_groups = db.query(models.Group).join(models.GroupMember).filter(
            models.GroupMember.user_id == user.id
        ).options(joinedload(models.Group.members)).all()

        # Calculate member counts
        for group in all_groups:
            group.member_count = len(group.members)

        for group in user_groups:
            group.member_count = len(group.members)

        print(f"Groups loaded: {len(all_groups)} total groups, {len(user_groups)} user groups")

        return templates.TemplateResponse(
            "groups.html",
            {
                "request": request,
                "user": user,
                "all_groups": all_groups,
                "user_groups": user_groups,
                "theme": theme
            }
        )

    except Exception as e:
        print(f"Error in groups_page: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Error loading groups page")


# Create group page
@app.get("/groups/create", response_class=HTMLResponse)
async def create_group_page(request: Request, db: Session = Depends(get_db)):
    try:
        print("Create group page requested")
        user = await get_current_user(request, db)
        if not user:
            return RedirectResponse(url="/login", status_code=303)

        theme = request.cookies.get("theme", "light")

        return templates.TemplateResponse(
            "create_group.html",
            {
                "request": request,
                "user": user,
                "theme": theme
            }
        )

    except Exception as e:
        print(f"Error in create_group_page: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Error loading create group page")


# Create a new group with cover image
@app.post("/api/groups")
async def create_group(
        request: Request,
        name: str = Form(...),
        description: Optional[str] = Form(None),
        cover_image: Optional[UploadFile] = File(None),
        db: Session = Depends(get_db)
):
    try:
        print(f"Creating group: {name}")
        user = await get_current_user(request, db)
        if not user:
            return RedirectResponse(url="/login", status_code=303)

        # Check if group name is already taken
        existing_group = db.query(models.Group).filter(models.Group.name == name).first()
        if existing_group:
            raise HTTPException(status_code=400, detail="Group name already taken")

        cover_image_url = None
        if cover_image and cover_image.filename:
            # Validate file type
            if not cover_image.content_type.startswith('image/'):
                raise HTTPException(status_code=400, detail="Only image files are allowed")

            # Save the uploaded file
            file_extension = cover_image.filename.split(".")[-1]
            filename = f"group_cover_{datetime.now().strftime('%Y%m%d%H%M%S')}.{file_extension}"
            file_path = f"static/uploads/groups/{filename}"

            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            with open(file_path, "wb") as buffer:
                content = await cover_image.read()
                buffer.write(content)

            cover_image_url = f"/static/uploads/groups/{filename}"

        # Create group
        db_group = models.Group(
            name=name,
            description=description,
            cover_image=cover_image_url,
            created_by=user.id,
            created_at=datetime.utcnow()
        )
        db.add(db_group)
        db.commit()
        db.refresh(db_group)

        # Add creator as admin member
        db_member = models.GroupMember(
            group_id=db_group.id,
            user_id=user.id,
            is_admin=True,
            joined_at=datetime.utcnow()
        )
        db.add(db_member)
        db.commit()

        print(f"Group created successfully: {db_group.id}")

        return RedirectResponse(url=f"/groups/{db_group.id}", status_code=303)

    except Exception as e:
        print(f"Error in create_group: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Error creating group")


# Group detail page
@app.get("/groups/{group_id}", response_class=HTMLResponse)
async def group_detail(
        group_id: int,
        request: Request,
        db: Session = Depends(get_db)
):
    try:
        print(f"Group detail requested for group_id: {group_id}")
        # Check authentication
        user = await get_current_user(request, db)
        if not user:
            return RedirectResponse(url="/login", status_code=303)

        theme = request.cookies.get("theme", "light")

        # Get group with members
        group = db.query(models.Group).options(
            joinedload(models.Group.members).joinedload(models.GroupMember.user)
        ).filter(models.Group.id == group_id).first()

        if not group:
            raise HTTPException(status_code=404, detail="Group not found")

        # Get creator info
        creator = db.query(models.User).filter(models.User.id == group.created_by).first()
        if creator:
            group.creator_name = creator.username
            group.creator_profile_picture = creator.profile_picture
        else:
            group.creator_name = "Unknown User"
            group.creator_profile_picture = "/static/default_profile.png"

        # Check if user is a member and admin status
        is_member = False
        is_admin = False

        member_record = db.query(models.GroupMember).filter(
            models.GroupMember.group_id == group_id,
            models.GroupMember.user_id == user.id
        ).first()

        if member_record:
            is_member = True
            is_admin = member_record.is_admin

        # Get group posts with proper relationships
        group_posts = db.query(models.Post).options(
            joinedload(models.Post.owner),
            joinedload(models.Post.likes),
            joinedload(models.Post.comments).joinedload(models.Comment.user)
        ).filter(models.Post.group_id == group_id).order_by(
            models.Post.created_at.desc()
        ).all()

        # Calculate like counts for each post
        for post in group_posts:
            post.like_count = len(post.likes) if post.likes else 0
            post.comment_count = len(post.comments) if post.comments else 0

            # Check if current user liked each post
            post.user_liked = False
            if post.likes:
                for like in post.likes:
                    if like.user_id == user.id:
                        post.user_liked = True
                        break

        # Get member count
        member_count = db.query(models.GroupMember).filter(
            models.GroupMember.group_id == group_id
        ).count()

        print(f"Group detail loaded: {member_count} members, {len(group_posts)} posts")

        return templates.TemplateResponse(
            "group_detail.html",
            {
                "request": request,
                "user": user,
                "group": group,
                "is_member": is_member,
                "is_admin": is_admin,
                "posts": group_posts,
                "member_count": member_count,
                "theme": theme
            }
        )

    except Exception as e:
        print(f"Error in group_detail: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal server error")


# Join/Leave group
@app.post("/api/groups/{group_id}/join")
async def join_group(
        group_id: int,
        request: Request,
        db: Session = Depends(get_db)
):
    try:
        print(f"Join/leave group requested for group_id: {group_id}")
        user = await get_current_user(request, db)
        if not user:
            return {"error": "Not authenticated"}

        group = db.query(models.Group).filter(models.Group.id == group_id).first()
        if not group:
            return {"error": "Group not found"}

        # Check if already a member
        existing_member = db.query(models.GroupMember).filter(
            models.GroupMember.group_id == group_id,
            models.GroupMember.user_id == user.id
        ).first()

        if existing_member:
            # Leave the group
            db.delete(existing_member)
            db.commit()
            member_count = db.query(models.GroupMember).filter(models.GroupMember.group_id == group_id).count()
            print(f"User left group: {group_id}, new member count: {member_count}")
            return {"joined": False, "member_count": member_count}
        else:
            # Join the group
            db_member = models.GroupMember(
                group_id=group_id,
                user_id=user.id,
                is_admin=False,
                joined_at=datetime.utcnow()
            )
            db.add(db_member)
            db.commit()
            member_count = db.query(models.GroupMember).filter(models.GroupMember.group_id == group_id).count()
            print(f"User joined group: {group_id}, new member count: {member_count}")
            return {"joined": True, "member_count": member_count}

    except Exception as e:
        print(f"Error in join_group: {str(e)}")
        print(traceback.format_exc())
        return {"error": "Internal server error"}


# Create a new post
@app.post("/api/posts")
async def create_post(
        request: Request,
        title: str = Form(...),
        content: str = Form(...),
        group_id: Optional[int] = Form(None),
        media: Optional[UploadFile] = File(None),
        db: Session = Depends(get_db)
):
    try:
        print(f"Creating post: {title}, group_id: {group_id}")
        user = await get_current_user(request, db)
        if not user:
            return RedirectResponse(url="/login", status_code=303)

        media_url = None
        media_type = None

        # Handle media upload
        if media and media.filename:
            # Validate file type
            if media.content_type.startswith('image/'):
                media_type = 'image'
            elif media.content_type.startswith('video/'):
                media_type = 'video'
            else:
                raise HTTPException(status_code=400, detail="Invalid file type. Only images and videos are allowed.")

            file_extension = media.filename.split(".")[-1]
            filename = f"post_{media_type}_{user.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.{file_extension}"
            file_path = f"static/uploads/posts/{filename}"

            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            # Read and save the file
            with open(file_path, "wb") as buffer:
                content_data = await media.read()
                buffer.write(content_data)

            media_url = f"/static/uploads/posts/{filename}"

        # Create post
        db_post = models.Post(
            title=title,
            content=content,
            image_url=media_url if media_type == 'image' else None,
            video_url=media_url if media_type == 'video' else None,
            owner_id=user.id,
            group_id=group_id,
            created_at=datetime.utcnow()
        )
        db.add(db_post)
        db.commit()
        db.refresh(db_post)

        print(f"Post created successfully: {db_post.id}")

        if group_id:
            return RedirectResponse(url=f"/groups/{group_id}", status_code=303)
        else:
            return RedirectResponse(url="/", status_code=303)

    except Exception as e:
        db.rollback()
        print(f"Error in create_post: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error creating post: {str(e)}")


# Like a post
@app.post("/api/posts/{post_id}/like")
async def like_post(
        post_id: int,
        request: Request,
        db: Session = Depends(get_db)
):
    try:
        print(f"Like post requested for post_id: {post_id}")
        user = await get_current_user(request, db)
        if not user:
            return {"error": "Not authenticated"}

        post = db.query(models.Post).filter(models.Post.id == post_id).first()
        if not post:
            return {"error": "Post not found"}

        # Check if already liked
        existing_like = db.query(models.Like).filter(
            models.Like.post_id == post_id,
            models.Like.user_id == user.id
        ).first()

        if existing_like:
            # Unlike the post
            db.delete(existing_like)
            db.commit()
            like_count = len(post.likes)
            print(f"Post unliked: {post_id}, like count: {like_count}")
            return {"liked": False, "like_count": like_count}
        else:
            # Like the post
            db_like = models.Like(
                post_id=post_id,
                user_id=user.id,
                created_at=datetime.utcnow()
            )
            db.add(db_like)
            db.commit()
            # Refresh the post to get updated like count
            db.refresh(post)
            like_count = len(post.likes)
            print(f"Post liked: {post_id}, like count: {like_count}")
            return {"liked": True, "like_count": like_count}

    except Exception as e:
        print(f"Error in like_post: {str(e)}")
        print(traceback.format_exc())
        return {"error": "Internal server error"}


# Add comment to a post
@app.post("/api/posts/{post_id}/comment")
async def add_comment(
        post_id: int,
        request: Request,
        content: str = Form(...),
        db: Session = Depends(get_db)
):
    try:
        print(f"Add comment requested for post_id: {post_id}")
        user = await get_current_user(request, db)
        if not user:
            return {"error": "Not authenticated"}

        post = db.query(models.Post).filter(models.Post.id == post_id).first()
        if not post:
            return {"error": "Post not found"}

        # Create comment
        db_comment = models.Comment(
            content=content,
            user_id=user.id,
            post_id=post_id,
            created_at=datetime.utcnow()
        )
        db.add(db_comment)
        db.commit()
        db.refresh(db_comment)

        print(f"Comment added successfully: {db_comment.id}")

        return {
            "success": True,
            "comment": {
                "id": db_comment.id,
                "content": db_comment.content,
                "created_at": db_comment.created_at.isoformat(),
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "profile_picture": user.profile_picture
                }
            }
        }

    except Exception as e:
        print(f"Error in add_comment: {str(e)}")
        print(traceback.format_exc())
        return {"error": "Internal server error"}


# Share a post
@app.post("/api/posts/{post_id}/share")
async def share_post(
        post_id: int,
        request: Request,
        db: Session = Depends(get_db)
):
    try:
        print(f"Share post requested for post_id: {post_id}")
        user = await get_current_user(request, db)
        if not user:
            return {"error": "Not authenticated"}

        original_post = db.query(models.Post).filter(models.Post.id == post_id).first()
        if not original_post:
            return {"error": "Post not found"}

        # Create a shared post
        db_post = models.Post(
            title=f"Shared: {original_post.title}",
            content=f"Shared from @{original_post.owner.username}: {original_post.content}",
            image_url=original_post.image_url,
            video_url=original_post.video_url,
            owner_id=user.id,
            created_at=datetime.utcnow()
        )
        db.add(db_post)
        db.commit()
        db.refresh(db_post)

        print(f"Post shared successfully: {db_post.id}")

        return {"success": True, "message": "Post shared successfully"}

    except Exception as e:
        print(f"Error in share_post: {str(e)}")
        print(traceback.format_exc())
        return {"error": "Internal server error"}


# Follow/Unfollow a user
@app.post("/api/users/{user_id}/follow")
async def follow_user(
        user_id: int,
        request: Request,
        db: Session = Depends(get_db)
):
    try:
        print(f"Follow user requested for user_id: {user_id}")
        user = await get_current_user(request, db)
        if not user:
            return {"error": "Not authenticated"}

        # Check if trying to follow self
        if user.id == user_id:
            return {"error": "Cannot follow yourself"}

        target_user = db.query(models.User).filter(models.User.id == user_id).first()
        if not target_user:
            return {"error": "User not found"}

        # Check if already following
        existing_follow = db.query(models.Follow).filter(
            models.Follow.follower_id == user.id,
            models.Follow.following_id == user_id
        ).first()

        if existing_follow:
            # Unfollow
            db.delete(existing_follow)
            db.commit()
            follower_count = len(target_user.followers)
            print(f"User unfollowed: {user_id}, follower count: {follower_count}")
            return {"following": False, "follower_count": follower_count}
        else:
            # Follow
            db_follow = models.Follow(
                follower_id=user.id,
                following_id=user_id,
                created_at=datetime.utcnow()
            )
            db.add(db_follow)
            db.commit()
            follower_count = len(target_user.followers)
            print(f"User followed: {user_id}, follower count: {follower_count}")
            return {"following": True, "follower_count": follower_count}

    except Exception as e:
        print(f"Error in follow_user: {str(e)}")
        print(traceback.format_exc())
        return {"error": "Internal server error"}


# Add this function to check if current user is following another user
def is_following(db: Session, follower_id: int, following_id: int) -> bool:
    try:
        return db.query(models.Follow).filter(
            models.Follow.follower_id == follower_id,
            models.Follow.following_id == following_id
        ).first() is not None
    except Exception as e:
        print(f"Error in is_following: {str(e)}")
        print(traceback.format_exc())
        return False

# Followers page
@app.get("/profile/{username}/followers", response_class=HTMLResponse)
async def followers_page(
        username: str,
        request: Request,
        db: Session = Depends(get_db)
):
    try:
        print(f"Followers page requested for username: {username}")
        user = await get_current_user(request, db)
        if not user:
            return RedirectResponse(url="/login", status_code=303)

        profile_user = db.query(models.User).filter(models.User.username == username).first()
        if not profile_user:
            raise HTTPException(status_code=404, detail="User not found")

        # Get followers with user details - FIXED: Use the correct relationship
        follower_records = db.query(models.Follow).options(
            joinedload(models.Follow.follower)  # This should match your model relationship name
        ).filter(models.Follow.following_id == profile_user.id).all()

        # Extract the actual user objects from the follow records
        followers = [record.follower for record in follower_records]

        theme = request.cookies.get("theme", "light")

        print(f"Followers loaded: {len(followers)} followers")

        return templates.TemplateResponse(
            "followers.html",
            {
                "request": request,
                "user": user,
                "profile_user": profile_user,
                "followers": followers,  # Pass the actual user objects
                "theme": theme,
                "page_type": "followers"
            }
        )

    except Exception as e:
        print(f"Error in followers_page: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Error loading followers page")
# Following page
@app.get("/profile/{username}/following", response_class=HTMLResponse)
async def following_page(
        username: str,
        request: Request,
        db: Session = Depends(get_db)
):
    try:
        print(f"Following page requested for username: {username}")
        user = await get_current_user(request, db)
        if not user:
            return RedirectResponse(url="/login", status_code=303)

        profile_user = db.query(models.User).filter(models.User.username == username).first()
        if not profile_user:
            raise HTTPException(status_code=404, detail="User not found")

        # Get following with user details - FIXED: Use the correct relationship
        following_records = db.query(models.Follow).options(
            joinedload(models.Follow.following_user)  # This should match your model relationship name
        ).filter(models.Follow.follower_id == profile_user.id).all()

        # Extract the actual user objects from the follow records
        following_users = [record.following_user for record in following_records]

        theme = request.cookies.get("theme", "light")

        print(f"Following loaded: {len(following_users)} following")

        return templates.TemplateResponse(
            "following.html",
            {
                "request": request,
                "user": user,
                "profile_user": profile_user,
                "following": following_users,  # Pass the actual user objects
                "theme": theme,
                "page_type": "following"
            }
        )

    except Exception as e:
        print(f"Error in following_page: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Error loading following page")



if __name__ == "__main__":
    import uvicorn

    print("Starting server with detailed logging...")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="debug")