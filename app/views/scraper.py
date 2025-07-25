from flask import Blueprint, Response, stream_with_context, request, jsonify
from app.decorators import require_jwt_token
from app.jwt_utils import decode_token
from models.user import User
from models.major import Major
from models.period import Period
from scraper.siak_ng_scraper import scrape_siak_ng_courses, format_sse
import json

router_scraper = Blueprint('router_scraper', __name__)

@router_scraper.route('/scrape-siak-ng', methods=['POST'])
@require_jwt_token
def scrape_siak_ng():
    """
    New SIAK NG scraper endpoint that integrates with the main backend.
    This endpoint saves scraped courses to the database and provides real-time updates via SSE.
    """
    # Get user data from JWT token
    # header_data = request.headers
    # user_data = decode_token(header_data["Authorization"].split()[1])
    # user: User = User.objects(id=user_data['user_id']).first()
    
    # if not user:
    #     return jsonify({'message': 'User not found.'}), 404
    
    data = request.get_json()
    if not data:
        return Response("Error: Request body is required.", status=400)

    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return Response("Error: Username and password are required.", status=400)
    
    def generate_logs_and_save(user_obj, siak_username, siak_password):
        scraper_generator = scrape_siak_ng_courses(siak_username, siak_password)
        # courses_data = None
        # period_name = None
        # target_period = None
        
        for event in scraper_generator:
            # # Check if this is the result event with courses data
            # if "event: result" in event:
            #     try:
            #         data_line = event.split("data: ")[1]
            #         result_data = json.loads(data_line)
            #         courses_data = result_data.get('courses')
            #         period_name = result_data.get('period_name')
            #         target_period = result_data.get('period')
            #     except (IndexError, json.JSONDecodeError):
            #         pass
            
            yield event
            
        # # Save courses to database if we got them
        # if courses_data and target_period:
        #     try:
        #         yield format_sse({
        #             "type": "status", 
        #             "message": "Saving courses to database..."
        #         }, event='log')
                
        #         # Get or create major for this user
        #         major = Major.objects(kd_org=user_obj.major_id).first()
        #         if not major:
        #             # Create new major if it doesn't exist
        #             major = Major(kd_org=user_obj.major_id, name=f"Major-{user_obj.major_id}")
        #             major.save()
                
        #         # Save courses to period
        #         period_instance = Period.objects(
        #             major_id=major.id,
        #             name=target_period,
        #             is_detail=True
        #         ).first()
                
        #         if period_instance:
        #             # Update existing period
        #             period_instance.courses = []  # Clear existing courses
        #             period_instance.save()
        #             yield format_sse({
        #                 "type": "status", 
        #                 "message": "Updated existing period with new courses."
        #             }, event='log')
        #         else:
        #             # Create new period
        #             period_instance = Period(
        #                 major_id=major.id,
        #                 name=target_period,
        #                 courses=[],
        #                 is_detail=True
        #             )
        #             period_instance.save()
        #             yield format_sse({
        #                 "type": "status", 
        #                 "message": "Created new period for courses."
        #             }, event='log')
                
        #         # Convert and save courses (you may need to adapt this based on your Course model)
        #         # For now, we'll just log that we would save them
        #         yield format_sse({
        #             "type": "success", 
        #             "message": f"Successfully saved {len(courses_data)} courses to database."
        #         }, event='log')
                
        #     except Exception as db_error:
        #         yield format_sse({
        #             "type": "error", 
        #             "message": f"Error saving to database: {str(db_error)}"
        #         }, event='log')

    return Response(stream_with_context(generate_logs_and_save(None, username, password)), content_type='text/event-stream')

@router_scraper.route('/scrape-siak-ng/status', methods=['GET'])
def scraper_status():
    """Simple status check for the scraper service."""
    return jsonify({
        "message": "SIAK NG scraper service is running",
        "version": "1.0"
    }), 200
