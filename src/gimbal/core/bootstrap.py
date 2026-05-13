# gimbal/bootstrap.py

def bootstrap(cli_args: dict[str, Any]) -> tuple[Engine, FrameworkContext]:
    """框架启动的完整初始化流程。
    
    职责:
    1. 加载并合并配置(ConfigLoader)
    2. 校验配置合法性
    3. 构造基础设施(EventBus/Archive/PluginRegistry)
    4. 初始化插件
    5. 创建 FrameworkContext
    6. 构造 Engine
    """
    
    # Step 1: 配置加载和合并
    loader = ConfigLoader()
    config = loader.load(
        cli_args=cli_args,
        project_config_path=cli_args.get("config"),
    )
    
    # Step 2: 打印配置来源(调试模式下)
    if cli_args.get("verbose"):
        for key, explanation in config.explain_all().items():
            print(f"  {explanation}")
    
    # Step 3: 构造基础设施
    event_bus = InMemoryEventBus()
    archive = MongoArchive(uri=config.mongo_uri)
    plugin_registry = PluginRegistry()
    
    # Step 4: 加载并初始化插件(插件向 EventBus 注册订阅)
    for plugin_name in config.plugins:
        plugin = plugin_registry.load(plugin_name)
        plugin.setup(event_bus, config=config.model_dump())
    
    # Step 5: 创建 ContextManager 和 FrameworkContext
    ctx_manager = ContextManager(archive=archive, event_bus=event_bus)
    framework_ctx = ctx_manager.create_framework_context(
        run_id=generate_run_id(),
        framework_version=GIMBAL_VERSION,
        config=config,
    )
    
    # Step 6: 构造 Engine
    engine = Engine(
        context_manager=ctx_manager,
        strategy_executor=StrategyExecutor(StrategyRegistry()),
        state_machine=StateMachine(),
    )
    
    return engine, framework_ctx