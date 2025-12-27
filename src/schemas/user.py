"""
User-related Pydantic schemas for authentication and profile management
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, validator


class UserBase(BaseModel):
    """Base user schema with common fields"""
    username: str = Field(..., min_length=3, max_length=50, description="Username, 3-50 characters")
    email: EmailStr = Field(..., description="User email address")
    preferred_model: Optional[str] = Field(default="qwen-max", description="Preferred LLM model")


class UserCreate(UserBase):
    """Schema for user registration"""
    password: str = Field(..., min_length=8, max_length=128, description="Password, 8-128 characters")

    @validator('username')
    def validate_username(cls, v):
        # Username should only contain alphanumeric characters, underscores, and hyphens
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Username can only contain alphanumeric characters, underscores, and hyphens')
        return v

    @validator('password')
    def validate_password(cls, v):
        # Password must contain at least one letter and one number
        if not any(c.isalpha() for c in v):
            raise ValueError('Password must contain at least one letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one number')
        return v


class UserLogin(BaseModel):
    """Schema for user login"""
    username: str = Field(..., description="Username or email address")
    password: str = Field(..., description="User password")


class UserUpdate(BaseModel):
    """Schema for user profile updates"""
    email: Optional[EmailStr] = Field(None, description="User email address")
    preferred_model: Optional[str] = Field(None, description="Preferred LLM model")


class UserResponse(BaseModel):
    """Schema for user profile response"""
    uuid: str = Field(..., description="User UUID")
    username: str = Field(..., description="Username")
    email: EmailStr = Field(..., description="User email")
    has_api_key: bool = Field(..., description="Whether user has configured an API key")
    preferred_model: str = Field(..., description="Preferred LLM model")
    created_at: datetime = Field(..., description="Account creation timestamp")

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """Schema for authentication token response"""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type (always 'bearer')")
    expires_in: int = Field(..., description="Token expiration time in seconds")
    user: UserResponse = Field(..., description="User profile information")


class LoginResponse(TokenResponse):
    """Schema for login response"""
    pass


class RegisterResponse(TokenResponse):
    """Schema for registration response"""
    pass


class UserProfile(UserResponse):
    """Schema for detailed user profile with additional fields"""
    api_key_configured: bool = Field(..., alias="has_api_key", description="Whether API key is configured")

    class Config:
        from_attributes = True
        use_enum_values = True


class APIKeyUpdate(BaseModel):
    """Schema for API key updates"""
    api_key: str = Field(..., min_length=20, description="DashScope API key")


class APIKeyUpdateResponse(BaseModel):
    """Schema for API key update response"""
    message: str = Field(..., description="Success message")
    api_key_configured: bool = Field(..., description="Whether API key is now configured")


class PreferencesUpdate(BaseModel):
    """Schema for preference updates"""
    preferred_model: Optional[str] = Field(None, description="Preferred LLM model")


class PreferencesUpdateResponse(BaseModel):
    """Schema for preference update response"""
    message: str = Field(..., description="Success message")
    preferred_model: str = Field(..., description="Updated preferred model")


class PasswordChange(BaseModel):
    """Schema for password change"""
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password, 8-128 characters")

    @validator('new_password')
    def validate_new_password(cls, v):
        # New password must contain at least one letter and one number
        if not any(c.isalpha() for c in v):
            raise ValueError('Password must contain at least one letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one number')
        return v


class PasswordChangeResponse(BaseModel):
    """Schema for password change response"""
    message: str = Field(..., description="Success message")


class MessageResponse(BaseModel):
    """Schema for simple message responses"""
    message: str = Field(..., description="Response message")


class UserListItem(BaseModel):
    """Schema for user list items (for admin endpoints)"""
    uuid: str = Field(..., description="User UUID")
    username: str = Field(..., description="Username")
    email: EmailStr = Field(..., description="Email")
    created_at: datetime = Field(..., description="Creation timestamp")
    file_count: int = Field(..., description="Number of files uploaded")
    task_count: int = Field(..., description="Number of tasks created")

    class Config:
        from_attributes = True