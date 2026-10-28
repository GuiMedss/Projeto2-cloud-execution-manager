Vagrant.configure("2") do |config|
  config.vm.box = "ubuntu/jammy64"
  config.vm.hostname = "cloud-execution-manager"

  # permite acessar o apache pelo navegador do computador
  config.vm.network "forwarded_port", guest: 80, host: 8080, host_ip: "127.0.0.1"

  # porta da aplicacao web
  config.vm.network "forwarded_port", guest: 3000, host: 3000, host_ip: "127.0.0.1"

  # o codigo sera baixado pelo git dentro da vm
  config.vm.synced_folder ".", "/vagrant", disabled: true

  config.vm.provider "virtualbox" do |vb|
    vb.name = "cloud-execution-manager"
    vb.memory = 4096
    vb.cpus = 1
    vb.gui = false
  end

  config.vm.provision "shell", path: "provision.sh"
end
