#!/usr/bin/env python3
"""
Simple debug script to test GDcards message parsing
"""

import sys
import os

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot.parsers import GDCardsParser, EnhancedGDCardsParser, UniversalParser

def test_simple_gdcards_parsing():
    """Test GDcards message parsing with simplified message"""
    
    # Simplified sample message without problematic characters
    sample_message = '''NOVAYA KARTA
-----------------
Igrok: TidalWaveT
-----------------
Karta: "Void Wave"
Opisanie: Proekt
Kategoria: Demony
-----------------
Redkost: Epicheskaya 
Ochki: +3
Kollekcia: 2/213 kart
-----------------
Limit kart segodnya: 1 iz 8'''
    
    print("Testing GDcards parsing...")
    print("=" * 50)
    print("Sample message:")
    print(sample_message)
    print("=" * 50)
    
    # Test with enhanced parser
    enhanced_parser = EnhancedGDCardsParser()
    enhanced_activities = enhanced_parser.parse_message(sample_message)
    
    print(f"Enhanced parser found {len(enhanced_activities)} activities")
    for i, activity in enumerate(enhanced_activities):
        print(f"Activity {i+1}:")
        print(f"  User: {activity.user_identifier}")
        print(f"  Type: {activity.activity_type}")
        print(f"  Points: {activity.points}")
        print(f"  Source: {activity.game_source}")
        print(f"  Metadata: {activity.metadata}")
        print()
    
    # Test with universal parser
    universal_parser = UniversalParser()
    universal_activities = universal_parser.parse_message(sample_message)
    
    print(f"Universal parser found {len(universal_activities)} activities")
    for i, activity in enumerate(universal_activities):
        print(f"Activity {i+1}:")
        print(f"  User: {activity.user_identifier}")
        print(f"  Type: {activity.activity_type}")
        print(f"  Points: {activity.points}")
        print(f"  Source: {activity.game_source}")
        print(f"  Metadata: {activity.metadata}")
        print()

def test_actual_gdcards_message():
    """Test with actual message format from user feedback"""
    
    # Message with actual format but plain text
    sample_message = '''NOVAYA KARTA
Igrok: TidalWaveT
Karta: "Void Wave"
Opisanie: Luchshiy proekt
Kategoria: Demony
Redkost: Epicheskaya
Ochki: +3
Kollekcia: 2/213 kart
Limit kart segodnya: 1 iz 8'''

    print("Testing with actual message format...")
    print("=" * 50)
    print("Sample message:")
    print(sample_message)
    print("=" * 50)
    
    # Test with enhanced parser
    enhanced_parser = EnhancedGDCardsParser()
    enhanced_activities = enhanced_parser.parse_message(sample_message)
    
    print(f"Enhanced parser found {len(enhanced_activities)} activities")
    for i, activity in enumerate(enhanced_activities):
        print(f"Activity {i+1}:")
        print(f"  User: {activity.user_identifier}")
        print(f"  Type: {activity.activity_type}")
        print(f"  Points: {activity.points}")
        print(f"  Source: {activity.game_source}")
        print(f"  Metadata: {activity.metadata}")
        print()

if __name__ == "__main__":
    print("Simple GDcards Parser Debug Script")
    print("=" * 50)
    
    test_simple_gdcards_parsing()
    print("\n" + "="*50 + "\n")
    test_actual_gdcards_message()
    
    print("Debug completed!")