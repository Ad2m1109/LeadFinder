import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

def generate_personalized_pitch(business_info: Dict[str, Any], query_category: str = "", query_city: str = "") -> str:
    """
    Generates a highly personalized cold email using deterministic rule-based logic.
    Zero API cost, zero rate limits, runs instantly locally.
    """
    name = business_info.get("name", "there")
    rating = business_info.get("rating", 0)
    reviews = business_info.get("reviews", 0)
    seo_score = business_info.get("seo_score", 0)
    seo_issues = business_info.get("seo_issues", "")
    has_website = bool(business_info.get("website"))
    
    # 1. Opening
    body = f"Hi {name} team,\n\n"
    
    category_text = f" {query_category}s" if query_category else " businesses"
    city_text = f" in {query_city}" if query_city else " in your area"
    
    body += f"I was researching top-rated{category_text}{city_text} and came across your profile. "
    
    # 2. Rating compliment (Hyper-personalization)
    if rating >= 4.5 and reviews > 10:
        body += f"I have to say, maintaining a {rating}-star rating with {reviews} reviews is incredibly impressive! You clearly run a tight ship.\n\n"
    elif reviews > 50:
        body += f"With {reviews} reviews, you are clearly a well-established staple in the community!\n\n"
    else:
        body += "I love what you guys are building.\n\n"
        
    # 3. The Pitch (Problem Detection & Solution)
    if not has_website:
        body += "I noticed that your Google Maps listing doesn't have a website attached. In 2024, a lot of potential customers will skip businesses without a professional web presence. We specialize in building affordable, high-converting websites for local businesses.\n"
    else:
        if seo_score > 0 and seo_score < 90:
            body += f"I took a quick look at your website and ran a tech audit. While it looks nice, I noticed a few technical issues holding you back (SEO Score: {seo_score}/100). "
            if "Missing Mobile Viewport" in seo_issues:
                body += "Most importantly, it seems your site isn't fully mobile-optimized, which means Google might penalize it in search rankings, and mobile users might leave immediately.\n"
            else:
                issue = seo_issues.split(",")[0]
                body += f"Specifically, the audit flagged: {issue}. These small technical fixes can make a huge difference in how high you rank on Google compared to your competitors.\n"
        else:
            body += "I took a look at your website and it looks great! However, we specialize in driving even more local traffic and optimizing conversion rates to turn those visitors into actual paying customers.\n"
            
    # 4. Call to action
    body += "\nWould you be open to a quick 5-minute chat this week to see how we could help you fix this and get more local customers through the door?\n\n"
    body += "Best regards,\n[Your Name]"
    
    return body
