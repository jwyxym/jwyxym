use std::{env, path::PathBuf, process::ExitCode, time::Duration};

use nexusmeta_inspect::{Component, Diagnostic, InspectError, Inspector, Report};

fn main() -> ExitCode {
	let path: Option<PathBuf> = env::args_os().nth(1).map(PathBuf::from);
	let path: PathBuf = match path {
		Some(path) => path,
		None => {
			eprintln!("用法：mod-info <模组.jar 或目录路径>");
			return ExitCode::FAILURE;
		}
	};
	let inspector: Inspector = match Inspector::with_timeout(Duration::from_secs(10)) {
		Ok(inspector) => inspector,
		Err(error) => {
			eprintln!("无法配置解析器：{error}");
			return ExitCode::FAILURE;
		}
	};
	let report: Report = match inspector.inspect(&path) {
		Ok(report) => report,
		Err(error) => {
			match error {
				InspectError::InvalidInput => eprintln!("文件不存在、输入无效或超过输入上限"),
				InspectError::LimitExceeded => eprintln!("解析过程超过资源上限"),
				InspectError::Timeout => eprintln!("解析超时"),
				_ => eprintln!("解析调用失败：{error}"),
			}
			return ExitCode::FAILURE;
		}
	};

	// invalid / partial / unrecognized 是报告状态，仍需读取诊断信息。
	println!("解析状态：{}", report.status);
	println!("输入 SHA256：{}", report.input_sha256);
	println!("输入大小：{} 字节", report.input_size);
	println!("组件数量：{}", report.components.len());
	report.components.iter().for_each(|component: &Component| {
		println!("\n名称：{}", component.display_name.as_deref().unwrap_or("未声明"));
		println!("ID：{}", component.id.as_deref().unwrap_or("未声明"));
		println!("版本：{}", component.version.as_deref().unwrap_or("未声明"));
		println!("类型：{}", component.kind);
		println!("加载器：{}", component.loader);
		println!("运行环境：{}", component.environment.as_deref().unwrap_or("未声明"));
		println!("描述文件：{}", component.descriptor_path);
		println!("约束：{:?}", component.constraints);
		println!("依赖：{}", component.dependencies);
	});
	report.diagnostics.iter().for_each(|diagnostic: &Diagnostic| {
		eprintln!("[{}] {}：{}", diagnostic.severity, diagnostic.code, diagnostic.message);
	});
	ExitCode::SUCCESS
}
