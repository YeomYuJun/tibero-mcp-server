import asyncio
import logging
import os
import jaydebeapi
from mcp.server import Server
from mcp.types import Resource, Tool, TextContent
from pydantic import AnyUrl

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("tibero_mcp_server")

def get_db_config():
    """Get database configuration from environment variables."""
    config = {
        "host": os.getenv("TIBERO_HOST", "localhost"),
        "port": os.getenv("TIBERO_PORT", "8629"),
        "sid": os.getenv("TIBERO_SID", "tibero"),
        "user": os.getenv("TIBERO_USER"),
        "password": os.getenv("TIBERO_PASSWORD")
    }
    
    if not all([config["user"], config["password"]]):
        logger.error("Missing required database configuration. Please check environment variables:")
        logger.error("TIBERO_USER and TIBERO_PASSWORD are required")
        raise ValueError("Missing required database configuration")
    
    return config

def get_connection():
    """Create a JDBC connection to Tibero database."""
    config = get_db_config()
    connection_string = f"jdbc:tibero:thin:@{config['host']}:{config['port']}:{config['sid']}"
    
    try:
        # Make sure the JDBC driver is in the classpath or provide path
        driver_path = os.getenv("CLASSPATH", "drivers/tibero6-jdbc.jar")
        
        conn = jaydebeapi.connect(
            "com.tmax.tibero.jdbc.TbDriver",
            connection_string,
            [config["user"], config["password"]],
            driver_path
        )
        conn.jconn.setAutoCommit(False)  # Set to manual commit mode for safety
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to Tibero: {str(e)}")
        raise

# Initialize server
app = Server("tibero_mcp_server")

@app.list_resources()
async def list_resources() -> list[Resource]:
    """List Tibero tables as resources."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get user tables
        cursor.execute("""
            SELECT table_name 
            FROM user_tables 
            ORDER BY table_name
        """)
        tables = cursor.fetchall()
        
        # Get user views
        cursor.execute("""
            SELECT view_name 
            FROM user_views 
            ORDER BY view_name
        """)
        views = cursor.fetchall()
        
        logger.info(f"Found {len(tables)} tables and {len(views)} views")
        
        resources = []
        
        # Add tables as resources
        for table in tables:
            resources.append(
                Resource(
                    uri=f"tibero://{table[0]}/data",
                    name=f"Table: {table[0]}",
                    mimeType="text/plain",
                    description=f"Data in table: {table[0]}"
                )
            )
            
        # Add views as resources
        for view in views:
            resources.append(
                Resource(
                    uri=f"tibero://{view[0]}/view",
                    name=f"View: {view[0]}",
                    mimeType="text/plain",
                    description=f"Data in view: {view[0]}"
                )
            )
            
        cursor.close()
        conn.close()
        return resources
    
    except Exception as e:
        logger.error(f"Failed to list resources: {str(e)}")
        return []

@app.read_resource()
async def read_resource(uri: AnyUrl) -> str:
    """Read table or view contents."""
    uri_str = str(uri)
    logger.info(f"Reading resource: {uri_str}")
    
    if not uri_str.startswith("tibero://"):
        raise ValueError(f"Invalid URI scheme: {uri_str}")
        
    parts = uri_str[9:].split('/')
    table_name = parts[0]
    resource_type = parts[1] if len(parts) > 1 else "data"
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get structure first
        cursor.execute(f"""
            SELECT column_name, data_type 
            FROM user_tab_columns 
            WHERE table_name = '{table_name.upper()}'
            ORDER BY column_id
        """)
        columns_info = cursor.fetchall()
        
        # Fetch sample data (limit to 100 rows for performance)
        cursor.execute(f"SELECT * FROM {table_name} WHERE ROWNUM <= 100")
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        
        # Format structure information
        structure = "TABLE STRUCTURE:\n"
        structure += "-" * 50 + "\n"
        structure += "COLUMN_NAME | DATA_TYPE\n"
        structure += "-" * 50 + "\n"
        for col_info in columns_info:
            structure += f"{col_info[0]} | {col_info[1]}\n"
        structure += "-" * 50 + "\n\n"
        
        # Format data
        data = "SAMPLE DATA:\n"
        data += ",".join(columns) + "\n"
        for row in rows:
            data += ",".join(map(str, row)) + "\n"
        
        cursor.close()
        conn.close()
        return structure + data
                
    except Exception as e:
        logger.error(f"Database error reading resource {uri}: {str(e)}")
        raise RuntimeError(f"Database error: {str(e)}")

@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available Tibero tools."""
    logger.info("Listing tools...")
    return [
        Tool(
            name="execute_sql",
            description="Execute an SQL query on the Tibero server",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The SQL query to execute"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="get_table_info",
            description="Get detailed information about a table",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "The name of the table"
                    }
                },
                "required": ["table_name"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute Tibero tools."""
    logger.info(f"Calling tool: {name} with arguments: {arguments}")
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        if name == "execute_sql":
            query = arguments.get("query")
            if not query:
                raise ValueError("Query is required")
            
            # Execute the query
            cursor.execute(query)
            
            # Handle different query types
            query_upper = query.strip().upper()
            
            # Data retrieval queries
            if (query_upper.startswith("SELECT") or 
                query_upper.startswith("SHOW") or 
                query_upper.startswith("DESC")):
                
                # Get column names
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                rows = cursor.fetchall()
                
                if not columns:
                    return [TextContent(type="text", text="Query executed successfully, but returned no columns.")]
                
                # Format as CSV
                result = [",".join(map(str, columns))]
                result.extend([",".join(map(lambda x: str(x) if x is not None else "NULL", row)) for row in rows])
                
                return [TextContent(
                    type="text", 
                    text=f"Results ({len(rows)} rows):\n" + "\n".join(result)
                )]
            
            # Non-SELECT queries (DML/DDL)
            else:
                # For DML, commit the transaction
                if (query_upper.startswith("INSERT") or 
                    query_upper.startswith("UPDATE") or 
                    query_upper.startswith("DELETE")):
                    conn.commit()
                    return [TextContent(
                        type="text", 
                        text=f"Query executed successfully. Rows affected: {cursor.rowcount}"
                    )]
                # For DDL, no commit needed (auto-commit)
                else:
                    return [TextContent(
                        type="text", 
                        text="Query executed successfully."
                    )]
        
        elif name == "get_table_info":
            table_name = arguments.get("table_name")
            if not table_name:
                raise ValueError("Table name is required")
            
            # Get table structure
            cursor.execute(f"""
                SELECT column_name, data_type, data_length, nullable
                FROM user_tab_columns 
                WHERE table_name = '{table_name.upper()}'
                ORDER BY column_id
            """)
            columns = cursor.fetchall()
            
            # Get constraint information
            cursor.execute(f"""
                SELECT c.constraint_name, c.constraint_type, 
                       cc.column_name
                FROM user_constraints c
                JOIN user_cons_columns cc ON c.constraint_name = cc.constraint_name
                WHERE c.table_name = '{table_name.upper()}'
                ORDER BY c.constraint_name, cc.position
            """)
            constraints = cursor.fetchall()
            
            # Get index information
            cursor.execute(f"""
                SELECT index_name, uniqueness
                FROM user_indexes
                WHERE table_name = '{table_name.upper()}'
            """)
            indexes = cursor.fetchall()
            
            # Format the results
            result = [f"Table: {table_name.upper()}", ""]
            
            result.append("COLUMNS:")
            result.append("-" * 80)
            result.append("NAME | TYPE | LENGTH | NULLABLE")
            result.append("-" * 80)
            for col in columns:
                nullable = "NULL" if col[3] == "Y" else "NOT NULL"
                result.append(f"{col[0]} | {col[1]} | {col[2]} | {nullable}")
            
            if constraints:
                result.append("")
                result.append("CONSTRAINTS:")
                result.append("-" * 80)
                result.append("NAME | TYPE | COLUMN")
                result.append("-" * 80)
                for con in constraints:
                    constraint_type = {
                        "P": "PRIMARY KEY",
                        "U": "UNIQUE",
                        "R": "FOREIGN KEY",
                        "C": "CHECK"
                    }.get(con[1], con[1])
                    result.append(f"{con[0]} | {constraint_type} | {con[2]}")
            
            if indexes:
                result.append("")
                result.append("INDEXES:")
                result.append("-" * 80)
                result.append("NAME | UNIQUENESS")
                result.append("-" * 80)
                for idx in indexes:
                    result.append(f"{idx[0]} | {idx[1]}")
            
            return [TextContent(type="text", text="\n".join(result))]
            
        else:
            raise ValueError(f"Unknown tool: {name}")
    
    except Exception as e:
        logger.error(f"Error executing tool '{name}': {e}")
        return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'conn' in locals() and conn:
            try:
                # Rollback any uncommitted changes to prevent accidental modifications
                if name == "execute_sql" and arguments.get("query", "").strip().upper().startswith("SELECT"):
                    pass  # No need to rollback for SELECT queries
                else:
                    conn.rollback()
            except:
                pass
            conn.close()

async def main():
    """Main entry point to run the MCP server."""
    from mcp.server.stdio import stdio_server
    
    logger.info("Starting Tibero MCP server...")
    config = get_db_config()
    logger.info(f"Database config: {config['host']}:{config['port']}/{config['sid']} as {config['user']}")
    
    async with stdio_server() as (read_stream, write_stream):
        try:
            await app.run(
                read_stream,
                write_stream,
                app.create_initialization_options()
            )
        except Exception as e:
            logger.error(f"Server error: {str(e)}", exc_info=True)
            raise

if __name__ == "__main__":
    asyncio.run(main())