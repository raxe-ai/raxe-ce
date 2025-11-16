#!/usr/bin/env python3
"""Demonstration of pure domain analytics functions.

This script shows how to use the domain layer for analytics calculations.
All functions are pure - no database, no network, just data in and data out.

Run this to verify the domain layer works correctly.
"""
from datetime import date, timedelta
from raxe.domain.analytics import (
    # Retention
    calculate_retention,
    calculate_cohort_retention,
    calculate_retention_rate,
    # Streaks
    calculate_streaks,
    compare_streaks,
    # Statistics
    calculate_dau,
    calculate_wau,
    calculate_mau,
    calculate_usage_statistics,
    calculate_stickiness,
    # Achievements
    ACHIEVEMENTS,
    calculate_user_achievements,
    find_next_achievements,
    get_leaderboard_points,
)


def demo_retention():
    """Demonstrate retention calculations."""
    print("\n" + "=" * 60)
    print("RETENTION METRICS DEMO")
    print("=" * 60)

    install_date = date(2025, 1, 1)
    scan_dates = [
        date(2025, 1, 2),   # Day 1
        date(2025, 1, 8),   # Day 7
        date(2025, 1, 15),  # Random scan
        date(2025, 1, 31),  # Day 30
    ]

    metrics = calculate_retention(
        installation_id="demo_user",
        install_date=install_date,
        scan_dates=scan_dates,
    )

    print(f"\nUser: {metrics.installation_id}")
    print(f"Installed: {metrics.install_date}")
    print(f"Total scans: {metrics.total_scans}")
    print(f"Last scan: {metrics.last_scan_date}")
    print(f"\nRetention:")
    print(f"  Day 1:  {'✓' if metrics.day1_retained else '✗'}")
    print(f"  Day 7:  {'✓' if metrics.day7_retained else '✗'}")
    print(f"  Day 30: {'✓' if metrics.day30_retained else '✗'}")


def demo_streaks():
    """Demonstrate streak calculations."""
    print("\n" + "=" * 60)
    print("STREAK METRICS DEMO")
    print("=" * 60)

    # Create a 7-day streak, then a gap, then a 3-day current streak
    today = date(2025, 1, 20)
    scan_dates = [
        date(2025, 1, 1),
        date(2025, 1, 2),
        date(2025, 1, 3),
        date(2025, 1, 4),
        date(2025, 1, 5),
        date(2025, 1, 6),
        date(2025, 1, 7),  # 7-day streak
        # gap
        date(2025, 1, 18),
        date(2025, 1, 19),
        date(2025, 1, 20),  # 3-day current streak
    ]

    metrics = calculate_streaks(
        installation_id="demo_user",
        scan_dates=scan_dates,
        reference_date=today,
    )

    print(f"\nUser: {metrics.installation_id}")
    print(f"Total scan days: {metrics.total_scan_days}")
    print(f"Last scan: {metrics.last_scan_date}")
    print(f"\nStreaks:")
    print(f"  Current streak:  {metrics.current_streak} days 🔥")
    print(f"  Longest streak:  {metrics.longest_streak} days 🏆")


def demo_statistics():
    """Demonstrate usage statistics."""
    print("\n" + "=" * 60)
    print("USAGE STATISTICS DEMO")
    print("=" * 60)

    period_end = date(2025, 1, 31)
    period_start = date(2025, 1, 1)

    # Simulate scan data
    scan_dates_by_user = {
        "user1": [period_end, period_end - timedelta(days=1)],  # Active daily
        "user2": [period_end - timedelta(days=3)],  # Active weekly
        "user3": [period_end - timedelta(days=15)],  # Active monthly
        "user4": [period_end - timedelta(days=25)],  # Active monthly
        "user5": [period_start],  # Churned
    }

    stats = calculate_usage_statistics(
        scan_dates_by_user=scan_dates_by_user,
        period_start=period_start,
        period_end=period_end,
    )

    print(f"\nPeriod: {stats.period_start} to {stats.period_end}")
    print(f"\nActive Users:")
    print(f"  DAU (Daily):   {stats.dau} users")
    print(f"  WAU (Weekly):  {stats.wau} users")
    print(f"  MAU (Monthly): {stats.mau} users")
    print(f"\nEngagement:")
    print(f"  Total scans:        {stats.total_scans}")
    print(f"  Avg scans per user: {stats.avg_scans_per_user:.1f}")
    print(f"  Stickiness (DAU/MAU): {calculate_stickiness(stats.dau, stats.mau):.1f}%")


def demo_achievements():
    """Demonstrate achievement calculations."""
    print("\n" + "=" * 60)
    print("ACHIEVEMENTS DEMO")
    print("=" * 60)

    # Create a user with some accomplishments
    scan_count = 100
    streaks = calculate_streaks(
        installation_id="demo_user",
        scan_dates=[date(2025, 1, i) for i in range(1, 8)],  # 7-day streak
        reference_date=date(2025, 1, 7),
    )

    achievements = calculate_user_achievements(
        installation_id="demo_user",
        scan_count=scan_count,
        streak_metrics=streaks,
    )

    print(f"\nUser: {achievements.installation_id}")
    print(f"Total scans: {achievements.scan_count}")
    print(f"Longest streak: {achievements.streak_count} days")
    print(f"\nUnlocked Achievements ({len(achievements.unlocked_achievements)}):")

    for ach_id in achievements.unlocked_achievements:
        ach = next(a for a in ACHIEVEMENTS if a.id == ach_id)
        print(f"  ✓ {ach.name} - {ach.description} (+{ach.points} points)")

    print(f"\nTotal Points: {achievements.total_points} 🏆")

    # Show next achievements
    next_achs = find_next_achievements(achievements, max_results=3)
    print(f"\nNext Achievements to Unlock:")
    for ach, progress_needed in next_achs:
        if "scan_count" in ach.unlock_condition:
            print(f"  → {ach.name}: {progress_needed} more scans needed")
        elif "streak_count" in ach.unlock_condition:
            print(f"  → {ach.name}: {progress_needed} more streak days needed")


def demo_leaderboard():
    """Demonstrate leaderboard generation."""
    print("\n" + "=" * 60)
    print("LEADERBOARD DEMO")
    print("=" * 60)

    # Create some users with different achievement levels
    users = {}
    for i, (scan_count, streak_days) in enumerate([
        (1000, 30),   # Super user
        (100, 7),     # Power user
        (10, 3),      # Getting started
        (1, 0),       # Newbie
    ], start=1):
        streaks = calculate_streaks(
            installation_id=f"user{i}",
            scan_dates=[date(2025, 1, d) for d in range(1, min(streak_days + 1, 32))],
            reference_date=date(2025, 1, 31),
        )
        users[f"user{i}"] = calculate_user_achievements(
            installation_id=f"user{i}",
            scan_count=scan_count,
            streak_metrics=streaks,
        )

    leaderboard = get_leaderboard_points(users)

    print("\nTop Users by Points:\n")
    for rank, (user_id, points) in enumerate(leaderboard, start=1):
        medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else "  "
        print(f"{medal} #{rank}. {user_id}: {points} points")


def main():
    """Run all demonstrations."""
    print("\n" + "=" * 60)
    print("RAXE DOMAIN ANALYTICS - PURE FUNCTIONS DEMO")
    print("=" * 60)
    print("\nThis demo shows the pure domain layer in action.")
    print("All calculations are done in-memory with zero I/O.")
    print("No database, no network, just Python!")

    demo_retention()
    demo_streaks()
    demo_statistics()
    demo_achievements()
    demo_leaderboard()

    print("\n" + "=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)
    print("\nAll functions are pure, fast, and testable!")
    print("Ready to be integrated with infrastructure layer.\n")


if __name__ == "__main__":
    main()
