#!env python3
"""
Deletes all the "Pytest *" Reports and Queries that might left over from failed tests
"""
import argparse
import os
import sys

from oaaclient.client import OAAClient, OAAClientError

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.getenv("VEZA_URL"), help="URL endpoint for Veza Deployment")
    parser.add_argument("--dry-run", action="store_true", help="Only print, do not delete")
    args = parser.parse_args()

    veza_api_key = os.getenv("VEZA_API_KEY")
    if not veza_api_key:
        print("Could not load VEZA_API_KEY from environment", file=sys.stderr)
        sys.exit(1)

    try:
        veza_con = OAAClient(args.host, veza_api_key)
    except OAAClientError as e:
        print("Error connecting to Veza instance")
        print(e, file=sys.stderr)
        if e.details:
            print(e.details, file=sys.stderr)
        sys.exit(1)

    print("Cleaning up reports")
    report_list = veza_con.get_reports()
    for report in report_list:
        if report["name"].startswith("Pytest"):
            print(f"Deleting Report {report['name']} ({report['id']})")
            if args.dry_run:
                continue
            veza_con.delete_report(report["id"])

    print("Cleaning up Queries")
    query_list = veza_con.get_queries()
    for query in query_list:
        if query["name"].startswith("Pytest"):
            print(f"Deleting Query {query['name']} ({query['id']})")
            if args.dry_run:
                continue
            veza_con.delete_query(query["id"])

    print("Finished")

if __name__ == "__main__":
    main()