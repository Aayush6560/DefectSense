"""Data processing module with moderate complexity."""


def process_user_records(records, filter_active=True):
    """Process and filter user records.
    
    Args:
        records: List of user dictionaries.
        filter_active: If True, only return active users.
    
    Returns:
        Processed user records.
    """
    result = []
    for record in records:
        if not isinstance(record, dict):
            continue
        
        if 'name' not in record or 'status' not in record:
            continue
        
        if filter_active and record['status'] != 'active':
            continue
        
        processed = {
            'name': record['name'].strip() if record['name'] else 'Unknown',
            'email': record.get('email', ''),
            'status': record['status'],
            'score': calculate_user_score(record)
        }
        result.append(processed)
    
    return result


def calculate_user_score(user_record):
    """Calculate a user's risk/activity score.
    
    Args:
        user_record: Dictionary with user data.
    
    Returns:
        Numerical score between 0 and 100.
    """
    base_score = 50
    
    if user_record.get('status') == 'inactive':
        base_score -= 20
    elif user_record.get('status') == 'active':
        base_score += 10
    
    if user_record.get('login_count', 0) > 100:
        base_score += 15
    elif user_record.get('login_count', 0) < 5:
        base_score -= 10
    
    age = user_record.get('account_age_days', 0)
    if age > 365:
        base_score += 5
    
    return min(100, max(0, base_score))


def aggregate_metrics(user_list):
    """Aggregate statistics from user list.
    
    Args:
        user_list: List of processed users.
    
    Returns:
        Dictionary with aggregated metrics.
    """
    if not user_list:
        return {'total': 0, 'active': 0, 'avg_score': 0}
    
    active_count = sum(1 for u in user_list if u['status'] == 'active')
    total_score = sum(u['score'] for u in user_list if 'score' in u)
    avg_score = total_score / len(user_list) if user_list else 0
    
    return {
        'total': len(user_list),
        'active': active_count,
        'avg_score': round(avg_score, 2)
    }
