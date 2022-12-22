package test.domain.PO;

import lombok.Data;
import org.neo4j.ogm.annotation.NodeEntity;
import org.neo4j.ogm.annotation.Property;
import org.neo4j.ogm.annotation.Relationship;

import java.util.ArrayList;
import java.util.List;

@Data
@NodeEntity(label = "Person")
public class Person extends BaseNode{

    @Property(name = "born")
    private Long born;
    @Property(name = "name")
    private String name;

    @Relationship(type = "ACTED_IN")
    List<ACTED_IN> relationship = new ArrayList<>();
}
